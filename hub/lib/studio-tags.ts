/**
 * Per-studio approved tag + category reference lists.
 *
 * Mirrors the lookup tables in script_writer_app.py (_STUDIO_TAGS,
 * _STUDIO_CATEGORIES). The Streamlit UI surfaces these behind a
 * collapsed expander so editors don't have to alt-tab to the Grail
 * sheet to confirm a tag exists on the site.
 *
 * NOTE: changes to the Grail/site allow-list must be mirrored here.
 * The backend has no endpoint for these yet, so there's no single source
 * of truth — keep diffs synced.
 */

export type StudioKey = "FuckPassVR" | "VRHush" | "VRAllure" | "NaughtyJOI"

export const STUDIO_CATEGORIES: Record<StudioKey, string[]> = {
  FuckPassVR: [
    "8K", "Anal", "Asian", "Big Ass", "Big Tits", "Blonde", "Blowjob",
    "Body Cumshot", "Brunette", "Compilation", "Creampie", "Cum on Tits",
    "Curvy", "Ebony", "Facial Cumshot", "Hairy Pussy", "Handjob", "Latina",
    "MILF", "Natural Tits", "Petite", "Redhead", "Small Tits", "Threesome",
  ],
  VRHush: [
    "8K", "Anal", "Asian", "Big Ass", "Big Tits", "Blonde", "Blowjob",
    "Body Cumshot", "Brunette", "Compilation", "Creampie", "Cum in Mouth",
    "Cum on Tits", "Cumshot", "Curvy", "Ebony", "Facial Cumshot",
    "Hairy Pussy", "Handjob", "Hardcore", "Latina", "MILF", "Natural Tits",
    "Oral Creampie", "Petite", "Redhead", "Shaved Pussy", "Small Tits",
    "Threesome",
  ],
  VRAllure: [
    "Anal", "Asian", "Big Ass", "Big Tits", "Blonde", "Blowjob",
    "Brunette", "Compilation", "Curvy", "Ebony", "Hairy Pussy", "Handjob",
    "Latina", "Masturbation", "MILF", "Natural Tits", "Petite", "Redhead",
    "Sex Toys", "Shaved Pussy", "Small Tits",
  ],
  NaughtyJOI: [],
}

export const STUDIO_TAGS: Record<StudioKey, string> = {
  FuckPassVR: "8K, African, American, Anal Creampie, Analized, Arab, Argentinian, Asia, Asian, Ass, Ass Bounce, Ass Eating, Ass Fucking, Ass to Mouth, Ass Worship, Athletic, ATM, Australian, Average, Babe, Bald Pussy, Ball Sucking, Bangkok, Beauty Pageant, Belarusian, Belgian, Belgium, Berlin, Big Boobs, Big Fake Tits, Big Natural Tits, Big Oiled Tits, Black, Black Eyes, Blonde, Blue Eyes, Boobjob, Braces, Brazilian, British, Brown Eyes, Brunette, Brunette Fuck, Budapest, Bush, Butt Fuck, Butt Plug, Canadian, Caucasian, Chair Grind, Chile, Chilean, Chinese, Chubby, Clean Pussy, Clit Piercing, Close-up, Colombian, Columbian, Compilation, Cooking, Cowgirl, Creampie, Croatian, Cuban, Cum Eating, Cum in Mouth, Cum In Pussy, Cum on Ass, Cum on Face, Cum Play, Cum Swallow, Cumplay, Czech, Czech Republic, Dancing, Deep Anal, Deep Throat, Deep Throating, Deepthroat, Dick Sucking, Doggy, Doggy Style, Doggystyle, Dutch, Eating Ass, Ebony Babe, Escort, Euro Babe, European, Face Fucking, Face in Camera, Facefuck, Facial, Fake Tits, Farmer's Daughter, FFM porn, Filipina, Filipino, Finger Play, Fingering, Finnish, Fishnet Stockings, Foot Job, Footjob, Freckles, French, German, GFE, Glasses, Green Eyes, Grey Eyes, Grinding, Hair Pulling, Hairy Pussy, Hand Job, Hazel Eyes, Hispanic, Hot Tub, Humping, Hungarian, Intimate, Italian, Italy, Japanese, Jerk to Pop, Jizz Shot, Kenyan, Kissing, Landing Strip, Lap Dance, Latin, Latin Pussy, Latvian, Lingerie, Long Hair, Long Legs, Maid, Maltese, Massage, Massage Oil, Masseuse, Masturbation, Mexican, Mexico, Middle Eastern, Milf Porn, Missionary, Moldovan, Natural Boobs, Natural Tits, Navel Piercing, Nipple Piercing, Nipple Piercings, Nipple Play, Oil, Oil Massage, Oiled Tits, Oral Creampie, Panty Sniffing, Peruvian, Petite, PHAT Ass, Pierce Nipples, Pierced Clit, Pierced Nipples, Pierced Pussy, Pole Dancing, Polish, POV, POV BJ, Puerto Rican, Pull Out Cumshot, Pullout Cumshot, Pussy Eating, Pussy Fingering, Pussy Licking, Pussy Play, Pussy Spread, Pussy to Mouth, Pussy Worship, Redhead, Reverse Cowgirl, Rimjob, Roller Skates, Russian, Saudi, Saudi Arabian, Secretary, Septum Piercing, Sexy Asian, Sexy Blonde, Sexy Brunette, Sexy Ebony, Sexy Latina, Sexy Raven, Sexy Redhead, Sexy Redheads, Shaved, Shaved Pussy, Short Skirt, Sixty-nine, Slim, Sloppy Blowjob, Slovakian, Small Boobs, Small Natural Tits, South America, Spanish, Squirter, Standing Doggy, Standing Missionary, Stockings, Stripper, Stripper Pole, Stripping, Sucking Tits, Swallow, Syrian, Tall, Tattoo, Tattooed, Tattoos, Tease, Thailand, Tight Ass, Titjob, Tits in Face, Titty Fuck, Titty Sucking, Tittyjob, Toys, Trimmed, Trimmed Pussy, True 8K, Turkish, Turkish Babe, Twerking, Ukraine, Ukrainian, United States, Venezuelan, Vibrator, Wrestling",
  VRHush: "8K, American, Anal, Analized, Arab, Asian, Ass, Ass Bounce, Ass Fucking, Ass Worship, Ass to Mouth, Athletic, ATM, Average, Bald Pussy, Ball Sucking, Big Boobs, Big Fake Tits, Big Natural Tits, Black, Blue Eyes, Brazilian, Brown Eyes, Brunette Fuck, Bush, Butt Fuck, Butt Plug, Canadian, Caucasian, Chair Grind, Chinese, Chubby, Clean Pussy, Clit Piercing, Close-up, Compilation, Cowgirl, Creampie, Cuban, Cum Eating, Cum in Mouth, Cum In Pussy, Cum on Ass, Cum on Face, Cum on Tits, Cum Play, Cum Swallow, Czech, Dancing, Deep Anal, Deep Throat, Deepthroat, Dick Sucking, Doggy Style, Doggystyle, Dutch, Ebony, Escort, Euro Babe, European, Facial, Fake Tits, Filipina, Filipino, Fingering, Fishnet Stockings, Footjob, Freckles, GFE, Glasses, Green Eyes, Grey Eyes, Hairy Pussy, Hazel Eyes, Hispanic, Intimate, Italian, Japanese, Jerk to Pop, Kissing, Landing Strip, Latin, Lingerie, Maltese, Massage, Massage Oil, Masseuse, Masturbation, Middle Eastern, Milf Porn, Missionary, Natural Boobs, Natural Tits, Navel Piercing, Oral Creampie, PHAT Ass, POV, POV BJ, Pierced Clit, Pierced Nipples, Polish, Pull Out Cumshot, Pullout Cumshot, Puerto Rican, Pussy Eating, Pussy Fingering, Pussy Licking, Pussy Play, Pussy Spread, Pussy Worship, Reverse Cowgirl, Rimjob, Roleplay, Romanian, Russian, Sexy Asian, Sexy Blonde, Sexy Brunette, Sexy Ebony, Sexy Latina, Sexy Raven, Sexy Redhead, Shaved, Shaved Pussy, Short Skirt, Sixty-nine, Slim, Slovakian, Small Boobs, Small Natural Tits, Spanish, Standing Missionary, Stockings, Stripper, Stripper Pole, Stripping, Syrian, Tattoos, Threesome, Tight Ass, Titjob, Tits in Face, Titty Fuck, Titty Sucking, Tittyjob, Toys, Trimmed, Trimmed Pussy, True 8K, Twerking, Ukrainian, Vibrator",
  VRAllure: "8K, American, Anal, Arab, Asian, Ass, Ass Bounce, Ass Spread, Ass Worship, Athletic, Australian, Average, Bald Pussy, Big Boobs, Big Fake Tits, Big Natural Tits, Black, Blue Eyes, Brazilian, Brown Eyes, Brunette Fuck, Bush, Butt Plug, Canadian, Caucasian, Chinese, Chubby, Clean Pussy, Clit Piercing, Close-up, Colombian, Compilation, Cowgirl, Creampie, Cuban, Curvy, Dancing, Deep Anal, Dick Sucking, Dildo Penetration, Doggy Style, Ebony, Euro Babe, European, Fake Tits, Filipina, Filipino, Fingering, Fishnet Stockings, Footjob, French, GFE, Glasses, Green Eyes, Grey Eyes, Hairy Pussy, Hazel Eyes, Intimate, Italian, Japanese, Jerk Off Instructions, Ken Doll, Kissing, Landing Strip, Latin, Latina, Lingerie, Maltese, Masturbation, Middle Eastern, Milf Porn, Missionary, Mongolian, Natural Boobs, Natural Tits, Navel Piercing, Outdoors, PHAT Ass, POV, POV BJ, Pierced Clit, Pierced Nipples, Polish, Puerto Rican, Pussy Eating, Pussy Fingering, Pussy Licking, Pussy Play, Pussy Spread, Pussy Worship, Pussylick, Reverse Cowgirl, Russian, Saudi, Sexy Asian, Sexy Blonde, Sexy Brunette, Sexy Ebony, Sexy Latina, Sexy Raven, Sexy Redhead, Shaved, Shaved Pussy, Sixty-nine, Slim, Small Boobs, Small Natural Tits, Solo, Spanish, Standing Missionary, Stockings, Stripper, Stripper Pole, Stripping, Syrian, Tattoos, Teens, Tight Ass, Titjob, Titty Fuck, Toys, Trimmed, Trimmed Pussy, True 8K, Twerking, Vibrator, Voyeur",
  NaughtyJOI: "",
}
