@echo off
echo === Audio Post Setup ===
echo.

:: Check Python
python --version 2>NUL
if errorlevel 1 (
    echo Python not found. Install Python 3.11+ from python.org then re-run this.
    pause
    exit /b 1
)

:: Install PyTorch with CUDA for RTX 3080 Ti
echo Installing PyTorch (CUDA 11.8)...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

:: Install remaining deps
echo Installing audio deps...
pip install silero-vad soundfile scipy numpy

:: Install speaker model deps
echo Installing speaker model deps...
pip install speechbrain huggingface_hub transformers accelerate

echo.
echo Done. Run workflow:
echo   Step 1 - Build speaker dataset:
echo     python build_speaker_dataset.py C:\audio_sessions --out C:\speaker_dataset
echo.
echo   Step 2 - Train speaker model:
echo     python train_speaker_model.py --dataset C:\speaker_dataset --out C:\speaker_model
echo.
echo   Step 3 - Process sessions:
echo     python patch_director_voice.py --dry-run "C:\audio_sessions\RiverLynn-DannySteele"
pause
