# Netherlands tools

## Label-bar masters

`composite_masters.py` replaces the gradient-scrim bake. It reads a pure pre-text PNG (no type, no scrim) and writes three finished masters. The photo pixels are not tinted or lettered. A 190px `#0e0e12` bar, with a 2px hairline, is added under the photo.

| Format | Canvas | Photo |
|--------|--------|-------|
| 16:9 | 1920×1270 | 1920×1080 |
| 4:5 | 864×1270 | 864×1080 |
| 9:16 | 1080×2110 | 1080×1920 |

Durable pre-text (kept in the repo):

```
library/pretext/Netherlands/<City>/<entry>-16x9.png
library/pretext/Netherlands/<City>/<entry>-4x5.png    # optional honest re-frame
library/pretext/Netherlands/<City>/<entry>-9x16.png   # optional honest re-frame
```

If only the 16:9 pre-text exists, 4:5 and 9:16 are center-cropped from it and resized with Lanczos. A format-specific file is used instead when the viewpoint needs its own frame. Do not crop a finished master to invent a pre-text.

Allura is vendored at `tools/fonts/Allura-Regular.ttf` (OFL, see `tools/fonts/OFL.txt`). The bar uses DejaVu Sans for the site line, scenario, disclosure, and “Jason D’s Vision”, and Allura for “Jason A. Devlin”.

Art. 50 metadata is five PNG chunks (Title and Copyright as iTXt, Description, Software, and Comment as tEXt), inserted before IEND after the image encode.

```
python3 tools/composite_masters.py NL-01-100 \
  --source path/to/pure-16x9.png \
  --source-4x5 path/to/pure-4x5.png \
  --source-9x16 path/to/pure-9x16.png

python3 tools/composite_masters.py NL-01-100 --check
```

Entry ids are required. `NL-01-001`–`010` and `NL-01-026`–`055` are refused unless `--allow-locked` is passed. Caption and the scenario line come from `tools/catalogue.json` and `evidence/weather/<id>.json`. The weather JSON is not rewritten.

Finished masters:

```
library/world/Netherlands/<City>/<entry>-16x9.png
library/world/Netherlands/<City>/<entry>-4x5.png
library/world/Netherlands/<City>/<entry>-9x16.png
```
