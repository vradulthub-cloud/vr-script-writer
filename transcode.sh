#!/opt/homebrew/bin/bash
# For Intel Macs, use:
# #!/usr/local/bin/bash

# Check for Bash version >= 4
if (( BASH_VERSINFO[0] < 4 )); then
    echo "This script requires Bash version 4 or higher. Current version: $BASH_VERSION"
    exit 1
fi

# Check FFmpeg installation
ffmpeg_path=$(which ffmpeg)
if [[ -z "$ffmpeg_path" ]]; then
    echo "ffmpeg not found. Please install ffmpeg via Homebrew: brew install ffmpeg"
    exit 1
fi

echo "Using Bash version: $BASH_VERSION"
echo "Using FFmpeg at: $ffmpeg_path"

# Configuration
CONCURRENT_JOBS=1  # Number of concurrent transcoding jobs
INPUT_PATH=""
AUTO=true

# Define default parameters
declare -A DEFAULTS=(
    ["c:a"]="aac"
    ["b:a"]="317k"
    ["aspect:v"]="2"
    ["movflags"]="+faststart"
    ["pass"]="1"
)

# Define output formats with VideoToolbox encoders
declare -A OUTPUTS_1K=(
    ["c:v"]="h264_videotoolbox"
    ["b:v"]="4.5M"
    ["minrate"]="4.5M"
    ["maxrate"]="4.5M"
    ["bufsize"]="9M"
    ["profile:v"]="baseline"
    ["pix_fmt"]="yuv420p"
    ["coder"]="0"
    ["filter:v"]="scale=1920:960"
    ["ac"]="2"
)

declare -A OUTPUTS_2K=(
    ["c:v"]="h264_videotoolbox"
    ["b:v"]="15M"
    ["minrate"]="15M"
    ["bufsize"]="30M"
    ["profile:v"]="main"
    ["pix_fmt"]="yuv420p"
    ["coder"]="0"
    ["filter:v"]="scale=2880:1440"
    ["ac"]="2"
)

declare -A OUTPUTS_4K=(
    ["c:v"]="h264_videotoolbox"
    ["b:v"]="28.1M"
    ["minrate"]="28.1M"
    ["bufsize"]="56.2M"
    ["profile:v"]="main"
    ["pix_fmt"]="yuv420p"
    ["coder"]="0"
    ["filter:v"]="scale=3840:1920"
)

declare -A OUTPUTS_8KHD=(
    ["c:v"]="hevc_videotoolbox"
    ["b:v"]="40M"
    ["minrate"]="40M"
    ["bufsize"]="80M"
    ["profile:v"]="main10"
    ["pix_fmt"]="yuv420p10le"
    ["filter:v"]="scale=7680:3840"
)

declare -A OUTPUTS_8KUHD=(
    ["c:v"]="hevc_videotoolbox"
    ["b:v"]="90M"
    ["minrate"]="90M"
    ["bufsize"]="130M"
    ["profile:v"]="main10"
    ["pix_fmt"]="yuv420p10le"
    ["filter:v"]="scale=8192:4096"
)

# Function to display usage
usage() {
    echo "Usage: $0 -i <input_path> [-a]"
    echo "  -i <input_path>  : Path to the input directory containing video files."
    echo "  -a               : Enable auto mode."
    exit 1
}

# Function to parse command-line arguments
parse_args() {
    while getopts ":i:a" opt; do
        case ${opt} in
            i )
                INPUT_PATH="$OPTARG"
                ;;
            a )
                AUTO=true
                ;;
            \? )
                echo "Invalid Option: -$OPTARG" 1>&2
                usage
                ;;
            : )
                echo "Invalid Option: -$OPTARG requires an argument" 1>&2
                usage
                ;;
        esac
    done
    shift $((OPTIND -1))

    if [[ -z "$INPUT_PATH" ]]; then
        echo "Error: Input path is required." 1>&2
        usage
    fi
}

# Function to initialize output formats
initialize_outputs() {
    OUTPUT_FORMATS=("1k" "2k" "4k" "8kHD" "8kUHD")
}

# Function to get transcoding parameters
get_parameters() {
    local format=$1
    declare -A params=()

    # Start with default parameters
    for key in "${!DEFAULTS[@]}"; do
        params["$key"]="${DEFAULTS[$key]}"
    done

    # Add/override with format-specific parameters
    case "$format" in
        "1k")
            for key in "${!OUTPUTS_1K[@]}"; do
                params["$key"]="${OUTPUTS_1K[$key]}"
            done
            ;;
        "2k")
            for key in "${!OUTPUTS_2K[@]}"; do
                params["$key"]="${OUTPUTS_2K[$key]}"
            done
            ;;
        "4k")
            for key in "${!OUTPUTS_4K[@]}"; do
                params["$key"]="${OUTPUTS_4K[$key]}"
            done
            ;;
        "8kHD")
            for key in "${!OUTPUTS_8KHD[@]}"; do
                params["$key"]="${OUTPUTS_8KHD[$key]}"
            done
            ;;
        "8kUHD")
            for key in "${!OUTPUTS_8KUHD[@]}"; do
                params["$key"]="${OUTPUTS_8KUHD[$key]}"
            done
            ;;
        *)
            echo "Unknown format: $format" 1>&2
            ;;
    esac

    # Output parameters as key=value pairs
    for key in "${!params[@]}"; do
        echo "$key=${params[$key]}"
    done
}

# Function to transcode a single file to a specific format
transcode_file() {
    local input_file=$1
    local format=$2
    local output_file=$3
    declare -A params=()

    # Populate params associative array
    while IFS='=' read -r key value; do
        params["$key"]="$value"
    done < <(get_parameters "$format")

    # Build ffmpeg command
    cmd="$ffmpeg_path -hide_banner -y -i \"$input_file\""

    for key in "${!params[@]}"; do
        value="${params[$key]}"
        # Handle parameters that require arguments
        if [[ "$key" == "filter:v" || "$key" == "movflags" || "$key" == "pass" ]]; then
            cmd+=" -$key \"$value\""
        else
            cmd+=" -$key $value"
        fi
    done

    cmd+=" \"$output_file\""

    # Execute ffmpeg command and log output
    echo "Transcoding '$input_file' to '$output_file'..."
    echo "$cmd" >> "${output_file}.log" 2>&1
    eval $cmd >> "${output_file}.log" 2>&1

    if [[ $? -eq 0 ]]; then
        echo "Successfully transcoded to '$output_file'."
    else
        echo "Failed to transcode '$input_file' to '$output_file'. Check log for details."
    fi
}

# Function to manage concurrent jobs
run_jobs() {
    local jobs=("$@")
    local current_jobs=()

    for job in "${jobs[@]}"; do
        # Start job in background
        eval "$job &"
        pid=$!
        current_jobs+=($pid)

        # If we've reached the concurrency limit, wait for any job to finish
        if [[ ${#current_jobs[@]} -ge $CONCURRENT_JOBS ]]; then
            wait -n
            # Remove finished PIDs from current_jobs
            for i in "${!current_jobs[@]}"; do
                if ! kill -0 "${current_jobs[$i]}" 2>/dev/null; then
                    unset 'current_jobs[i]'
                fi
            done
        fi
    done

    # Wait for all remaining jobs to finish
    wait
}

# Main Script Execution
parse_args "$@"
initialize_outputs

# Find all .mp4 and .mov files in the input path (non-recursive)
masters=()
while IFS= read -r file; do
    masters+=("$file")
done < <(find "$INPUT_PATH" -maxdepth 1 -type f \( -iname "*.mp4" -o -iname "*.mov" \))

if [[ ${#masters[@]} -eq 0 ]]; then
    echo "No video files found in '$INPUT_PATH'."
    exit 1
fi

# Create output directory
dir_processed="$INPUT_PATH/Processed"
mkdir -p "$dir_processed"

# Prepare list of transcoding jobs
declare -a transcoding_jobs=()

for master in "${masters[@]}"; do
    base_name=$(basename "$master")
    base_no_ext="${base_name%.*}"

    for format in "${OUTPUT_FORMATS[@]}"; do
        output_filepath="$dir_processed/${base_no_ext}_${format}.mp4"

        # Skip if output already exists and matches duration (allowing 1 second difference)
        if [[ -f "$output_filepath" ]]; then
            input_duration=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$master")
            output_duration=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$output_filepath")

            # Compare durations
            duration_diff=$(echo "$input_duration - $output_duration" | bc)
            duration_diff=${duration_diff#-}  # Absolute value

            if (( $(echo "$duration_diff < 1" | bc -l) )); then
                echo "Output '$output_filepath' already exists and matches duration. Skipping..."
                continue
            fi
        fi

        # Define transcoding command
        job="transcode_file \"$master\" \"$format\" \"$output_filepath\""
        transcoding_jobs+=("$job")
    done
done

# Execute transcoding jobs with concurrency
run_jobs "${transcoding_jobs[@]}"

echo "All transcoding jobs completed."

# Optional: Display a notification (uncomment if desired)
# osascript -e 'display notification "Transcoding completed." with title "FFmpeg Transcoder"'

# Prompt to exit
read -n 1 -s -r -p "Press any key to continue..."
echo

