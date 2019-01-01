
# Azulejo
Simple Python tool to generate mosaic version of a photograph.

# Dependencies

* Python's OpenCV (tested with python 2.7 and OpenCV 2.4.9.1)

# Usage
##  Help
For a list of options: ` python main.py --help `

## Common usage
Most common usage usage is
```python main.py --library my_photo_directory/ --source source_image.png --dest my_beautiful_mosaic.jpg```

## List of options
* `--thumb-size w,h`: configure mosaic tile width to **w** and height to **h**
* `--source-coeff s `, `--mosaic-coeff m`: the final image is made by blending source into the generated mosaic with the following formulae: **dest = s * source + m * mosaic**
* `--metric <sub|average|palette> `: chose the metric to compute closest tile between source and library
