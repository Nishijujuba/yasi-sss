from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "resources" / "剑桥" / "剑桥雅思10"
SPLIT_PDF_ROOT = SOURCE_ROOT / "剑桥雅思真题10分P"
QUESTION_PDF = SPLIT_PDF_ROOT / "02_Test_1_p010-p032.pdf"
TEST2_PDF = SPLIT_PDF_ROOT / "03_Test_2_p033-p056.pdf"
AUDIOSCRIPT_PDF = SPLIT_PDF_ROOT / "08_Audioscripts_p130-p150.pdf"
ANSWER_KEY_PDF = SPLIT_PDF_ROOT / "09_Listening_and_Reading_Answer_Keys_p151-p160.pdf"
AUDIO_SOURCE_ROOT = SOURCE_ROOT / "剑桥雅思10音频" / "test1"

PACK_ROOT = ROOT / "public" / "packs" / "cambridge-10" / "test-1" / "listening"
TEST2_PACK_ROOT = ROOT / "public" / "packs" / "cambridge-10" / "test-2" / "listening"
PAGE_ASSET_ROOT = PACK_ROOT / "assets" / "pages"
TEST2_PAGE_ASSET_ROOT = TEST2_PACK_ROOT / "assets" / "pages"
AUDIO_ASSET_ROOT = PACK_ROOT / "assets" / "audio"
SOURCE_DATA_ROOT = ROOT / "builder" / "source_data"
SCHEMA_ROOT = ROOT / "builder" / "schemas"
REVIEW_ROOT = ROOT / "build" / "review"

FFMPEG = Path(r"D:\Project\video2pdf\kimi\tools\ffmpeg\bin\ffmpeg.exe")
FFPROBE = Path(r"D:\Project\video2pdf\kimi\tools\ffmpeg\bin\ffprobe.exe")
PDFTOPPM = Path(r"D:\kits\MiKTex\miktex\bin\x64\pdftoppm.exe")

SCHEMA_VERSION = 1
OVERLAY_CONFIDENCE_GATE = 0.85
QUESTION_PAGE_NUMBERS = tuple(range(10, 17))
TEST2_LISTENING_PAGE_NUMBERS = tuple(range(33, 41))
SECTION_QUESTION_RANGES = {
    1: range(1, 11),
    2: range(11, 21),
    3: range(21, 31),
    4: range(31, 41),
}
