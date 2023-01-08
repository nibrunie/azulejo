
# Azulejo
Simple Python tool to generate mosaic/tiled version of a photograph.

# Dependencies

* Python's OpenCV (tested with python 2.7 and OpenCV 2.4.9.1)

# Usage
##  Help
For a list of options: ` python main.py --help `

## Common usage

### generating still picture 

Most common usage usage is
```python main.py --library my_photo_directory/ --source source_image.png image --output my_beautiful_mosaic.jpg ```

### generating video (transition from source to mosaic)

```
python3 main.py  --tile-dir my_tiles_directory/ --source source_image.jpg \
                 --tile-angles "10,5,0,-5,-10" --tile-size 64,64  --fast video \
                 --num-frames 75 --extra-frames 125 --size 1920,1080 \
                 --output mosaic-video.avi
```

NOTE: if the `--library` option is omitted, azulejo expects to find a library of pre-build tiles in the tile directory (default `./.mosaic_libs` or can be specified through `--tile-dir` option) and no new tile will be generated. This results in a much faster execution time

### Common List of options
* `--tile-size w,h`: configure mosaic tile width to **w** and height to **h**
* `--source-coeff s `, `--mosaic-coeff m`: the final image is made by blending source into the generated mosaic with the following formulae: **dest = s * source + m * mosaic**
* `--metric <sub|average|palette> `: chose the metric to compute closest tile between source and library


