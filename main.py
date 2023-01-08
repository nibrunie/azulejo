import argparse
import cv2
import random
import math
import time
import re

import numpy as np

import os
from os.path import isfile, join


def parse_metric(metric_label):
    """ convert str to metric function """
    return {
        "average": average_metric,
        "palette": palette_metric,
        "sub": sub_metric,
    }[metric_label]

def parse_int_tuple(tuple_str):
    """ convert str to integer tuple """
    result = tuple(int(v) for v in tuple_str.split(","))
    assert len(result) == 2
    return result

def average_metric(img):
    """ return the value of a metric on an image """
    avg = img.mean(axis=0).mean(axis=0)
    return avg

def palette_metric(img):
    # determine a dominant "color" by clustering colors in 5 palettes
    n_colors = 5
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 200, .1)
    flags = cv2.KMEANS_RANDOM_CENTERS
    flatten_img = np.float32(img.view().reshape(-1, 3))

    _, labels, palette = cv2.kmeans(flatten_img, n_colors, criteria, 10, flags)
    _, counts = np.unique(labels, return_counts=True)
    dominant = palette[np.argmax(counts)]
    return dominant

def sub_metric(img):
    return cv2.resize(cv2.cvtColor(img, (cv2.COLOR_BGR2GRAY)), (4, 4)).reshape(1, -1)



def build_image_library(cfg, metric_fct, tile_angles, verbose=False, sampling=None):
    """ build a library of thumbnails 
        @param cfg configuration
        @param metric_fct
        @param angles
        @sampling (None: disabled) select a sub-sample of the library
        
        If a thumbnail has already been generated by a previous run, it will not be generated twice
        """
    if not os.path.isdir(cfg.tileDir):
        print("creating directory {}".format(cfg.tileDir))
        os.mkdir(cfg.tileDir)
    image_library = []
    pixel_library = [f for f in os.listdir(cfg.tileDir) if isfile(join(cfg.tileDir, f))]
    for dirpath, dirnames, filenames in os.walk(cfg.imgDir):
        for _f in filenames:
            filename = os.path.join(cfg.imgDir, dirpath, _f)
            if verbose: print("processing {}".format(filename))
            base = os.path.basename(filename)
            prefix, extension = os.path.splitext(base)
            extension = extension.lower()
            thumb_filename = prefix + "_{}x{}".format(cfg.tileW, cfg.tileH) + extension
            if extension in [".png", ".jpg"]:
                # only png and jpg image are processed
                if thumb_filename in pixel_library:
                    # check if a file with name matching thumbnail filename already exists
                    if verbose: print("pixel found in temporary library")
                    thumb = cv2.imread(join(cfg.tileDir, thumb_filename))
                else:
                    if verbose: print("pixel NOT found in temporary library")
                    try:
                        picture = cv2.imread(filename)
                        thumb = cv2.resize(picture, (cfg.tileW, cfg.tileH))
                        # saving thumbnail
                        cv2.imwrite(os.path.join(cfg.tileDir, thumb_filename), thumb)
                    except:
                        print(f"[error] unable to process {filename}")
                for rot_angle in tile_angles:
                    M = cv2.getRotationMatrix2D((cfg.tileW/2,cfg.tileH/2),rot_angle,1)
                    new_tile = cv2.warpAffine(thumb,M,(cfg.tileW,cfg.tileH))
                    metric = metric_fct(new_tile)
                    image_library.append((metric, new_tile))
    print("library, containing {} image(s), has been generated".format(len(image_library)))
    if sampling:
        return random.choices(image_library, k=sampling)
    else:
        return image_library


def load_pixel_library(tile_dir, metric_fct, tile_angles, verbose=False, sampling=None):
    """ load a library of thumbnails 
        @param tile_dir directory containing generated thumbnails
        @param metric_fct
        @param angles
        @sampling (None: disabled) select a sub-sample of the library
        
        If a thumbnail has already been generated by a previous run, it will not be generated twice
        """
    if not os.path.isdir(tile_dir):
        raise Exception(f"{tile_dir} does not exist")
    image_library = []
    pixel_library = [f for f in os.listdir(tile_dir) if isfile(join(tile_dir, f))]
    for thumb_filename in pixel_library:
        thumbMatch = re.match(".*_(?P<w>\d+)x(?P<h>\d+).(jpg|JPG|PNG|png)", thumb_filename)
        if thumbMatch:
            w = int(thumbMatch.group("w"))
            h = int(thumbMatch.group("h"))
            if w == cfg.tileW and h == cfg.tileH:
                if verbose: print(f"pixel {thumb_filename} with matching dimensions found in temporary library")
                thumb = cv2.imread(join(tile_dir, thumb_filename))
                for rot_angle in tile_angles:
                    M = cv2.getRotationMatrix2D((cfg.tileW/2,cfg.tileH/2),rot_angle,1)
                    new_tile = cv2.warpAffine(thumb,M,(cfg.tileW,cfg.tileH))
                    metric = metric_fct(new_tile)
                    image_library.append((metric, new_tile))
    print("library, containing {} image(s), has been generated".format(len(image_library)))
    if sampling:
        return random.choices(image_library, k=sampling)
    else:
        return image_library


def buildMosaicTiles(source, metric_fct, image_library, random_size=6, fast=False):
    """ Building a mozaic approximating the source image """
    # iterating over 2D tiles of the source image. each tile is cfg.tileW x cfg.tileH
    #   - for each tile select the closest library thumbnail
    #   - build the destination image by replacing each source tile by the selected thumbnail
    #
    # Two metrics are used:
    # - the first metric, dist, is used to select the <random_size> closest thumbnail to the local tile

    # metric linearization

    # determing for the 3D metric (color) a max and a min vector
    max_0 = max(m[0] for (m, t) in  image_library)
    max_1 = max(m[1] for (m, t) in  image_library)
    max_2 = max(m[2] for (m, t) in  image_library)
    min_0 = min(m[0] for (m, t) in  image_library)
    min_1 = min(m[1] for (m, t) in  image_library)
    min_2 = min(m[2] for (m, t) in  image_library)

    min_v = np.array([min_0, min_1, min_2])
    max_v = np.array([max_0, max_1, max_2])
    delta_v = max_v - min_v

    numTilesReq = (source.height / cfg.tileH) * (source.width / cfg.tileW)
    assert numTilesReq <= len(image_library), f"there should more tiles in the library ({len(image_library)} than the required number of tiles ({numTilesReq})"

    def tileLinearizedMetric(metric):
        # saturating the current vector metric between min and max value
        saturatedMetric = np.maximum(np.minimum(metric, max_v), min_v)
        # evaluating a scalar metric by normalizaing each component and generating a 3-digit number
        scalarMetric = np.dot((saturatedMetric - min_v) / delta_v, np.array([1, 2, 4]))
        return scalarMetric

    linImgLib = sorted(image_library, key=lambda metric_tile: tileLinearizedMetric(metric_tile[0]))
    linImgMetric = [tileLinearizedMetric(metric) for (metric, tile) in linImgLib]

    def retrieveTile(index):
        """ get and remove index-tile from library """
        tile = linImgLib.pop(index)
        linImgMetric.pop(index)
        return tile

    def getClosestTile(metric):
        # using a median pivot to locate in logarithm time, <random_size> closest
        # neighbours
        imgMaxIdx = len(linImgLib) # this needs to be evaluated here (and not factorized) as the tile could have been updated
        scalarMetric = tileLinearizedMetric(metric)
        idx = imgMaxIdx // 2
        idxSup = imgMaxIdx - 1
        idxInf = 0
        while idxSup - idxInf > random_size:
            if linImgMetric[idx] < scalarMetric:
                idxInf = idx 
            else:
                idxSup = idx
            idx = idxInf + (idxSup - idxInf) // 2
        idx = max(min(idx, imgMaxIdx - random_size // 2), random_size // 2)
        return max(0, min(random.randrange(idx - random_size // 2, idx + random_size // 2), imgMaxIdx-1))

    # retrieving the closest tile from each source tile
    tiles = {}
    for tile_y in range(source.height // cfg.tileH):
        for tile_x in range(source.width // cfg.tileW):
            x = tile_x * cfg.tileW
            y = tile_y * cfg.tileH
            local_thumb = source.data[y:(y+cfg.tileH), x:(x+cfg.tileW)]
            src_average = metric_fct(local_thumb)
            src_sub = sub_metric(local_thumb)
            def dist(lib_img):
                delta = src_average - lib_img[0]
                value = np.dot(delta, delta.transpose())
                # the actual distance should be math.sqrt(value) but since
                # we compare 2 distances, we can save the square root evaluation
                return value
            def sub_dist(lib_img):
                delta = src_sub - sub_metric(lib_img[1])
                value = np.dot(delta, delta.transpose())
                return math.sqrt(value)
            if fast:
                closestIdx = getClosestTile(src_average)
                closest = retrieveTile(closestIdx)[1] # retrieving and removing tile from the list to ensure it is only used once
            else:
                enumeratedLib = list((m, img, idx) for (idx, (m, img)) in enumerate(image_library))
                closest_list = sorted(enumeratedLib, key=dist)[:random_size]
                imgTriple = random.choice(closest_list)
                closest = imgTriple[1]
                image_library.pop(imgTriple[2]) # remove (metric, closest) to ensure each tile is only used once
            tiles[(tile_x, tile_y)] = closest
    return tiles

def generateSingleImage(cfg, source, tiles, stripes=None):
    # generate mosaic image
    dest = np.zeros((source.height, source.width, 3), np.uint8)
    NUM_TILES_X = source.width // cfg.tileW
    for tile_y in range(source.height // cfg.tileH):
        y = tile_y * cfg.tileH
        for tile_x in range(NUM_TILES_X):
            x = tile_x * cfg.tileW
            closest = tiles[(tile_x, tile_y)]
            local_thumb = source.data[y:(y+cfg.tileH), x:(x+cfg.tileW)]
            alphaThumb = 0.4
            alphaSource = 1 - alphaThumb
            dest[y:(y+cfg.tileH), x:(x+cfg.tileW)] = closest * alphaThumb + local_thumb * alphaSource
    # stripes
    addStripe = not stripes is None
    if addStripe:
        stripeWidth, nextStripe = stripes
        for stripe in range(0, source.width, stripeWidth):
            # p = stripe / source_width / 2
            # black = random.random() > (1 - p) 
            index = stripe // stripeWidth
            black = index == nextStripe
            if black:
                dest[0:source.height,stripe:stripe+stripeWidth] = 0
                nextStripe = index + max(int(50 * (1.0 - (index / (source.width // stripeWidth))**2)), 2)
    
    return dest

class AlphaGenerator:
    generators = {}
    def getAlpha(self, frameId, tile_x, tile_y):
        raise NotImplementedError

    @staticmethod
    def RegisteredAlphaGenerator(genCls):
        AlphaGenerator.generators[genCls.label] = genCls 
        return genCls

@AlphaGenerator.RegisteredAlphaGenerator
class WaveAlphaGenerator(AlphaGenerator):
    label = "wave"
    def __init__(self, cfg, videoCfg, sourceCfg, mosaicSplitDeltaFrames):
        self.cfg = cfg
        self.videoCfg = videoCfg
        self.mosaicSplitDeltaFrames = mosaicSplitDeltaFrames
        self.NUM_TILES_X = sourceCfg.width // cfg.tileW

    def updateToFrame(self, frameId):
        # number of frames between the time a column of tiles start to appear as mosaic
        # (with the source image still having the majority of alpha) and the time the
        # tile column only appear as mosaic (alpha source = 0.0)
        self.splitStartXRaw   = 1 - frameId / (self.videoCfg.numFrames - 1 - self.mosaicSplitDeltaFrames)
        self.splitStartX      = max(0, self.splitStartXRaw)
        self.splitStopX       = min(1, 1 - (frameId - self.mosaicSplitDeltaFrames) / (self.videoCfg.numFrames - 1 - self.mosaicSplitDeltaFrames))
        self.tileStartIdx     = int(self.splitStartX * self.NUM_TILES_X)
        self.tileStopIdx      = int(self.splitStopX  * self.NUM_TILES_X)

    def getAlpha(self, frameId, tile_x, tile_y):
        deltaAlpha = self.cfg.maxAlphaTile - self.cfg.minAlphaTile
        x = tile_x * cfg.tileW
        if tile_x < self.tileStartIdx:
            alphaThumb = self.cfg.minAlphaTile
        elif tile_x >= self.tileStopIdx:
            alphaThumb = self.cfg.maxAlphaTile
        else:
            alphaThumb = self.cfg.minAlphaTile + (deltaAlpha) * max(0, min(1, (x / source.width - self.splitStartXRaw) / (self.mosaicSplitDeltaFrames / self.videoCfg.numFrames)))
        return alphaThumb


@AlphaGenerator.RegisteredAlphaGenerator
class RandomAlphaGenerator(AlphaGenerator):
    label = "random"
    def __init__(self, cfg, videoCfg, sourceCfg, mosaicSplitDeltaFrames):
        self.cfg = cfg
        self.videoCfg = videoCfg
        self.mosaicSplitDeltaFrames = mosaicSplitDeltaFrames
        self.NUM_TILES_X = sourceCfg.width // cfg.tileW
        self.NUM_TILES_Y = sourceCfg.height // cfg.tileH
        maxStartFrame = (self.videoCfg.numFrames - mosaicSplitDeltaFrames)
        self.startFrame         = [[int(random.random() * maxStartFrame) for i in range(self.NUM_TILES_Y)] for j in range(self.NUM_TILES_X)]
        self.deltaAlphaPerFrame = [[1 / ((0.5 + 0.5 * random.random()) * mosaicSplitDeltaFrames) for i in range(self.NUM_TILES_Y)] for j in range(self.NUM_TILES_X)]

    def updateToFrame(self, frameId):
        pass

    def getAlpha(self, frameId, tile_x, tile_y):
        if frameId < self.startFrame[tile_x][tile_y]:
            alphaThumb = self.cfg.minAlphaTile
        else:
            alphaOffset = (frameId - self.startFrame[tile_x][tile_y]) * self.deltaAlphaPerFrame[tile_x][tile_y]
            alphaThumb = min(self.cfg.maxAlphaTile, self.cfg.minAlphaTile + (self.cfg.maxAlphaTile - self.cfg.minAlphaTile) * alphaOffset)
        return alphaThumb
    

@AlphaGenerator.RegisteredAlphaGenerator
class FireworksAlphaGenerator(RandomAlphaGenerator):
    label = "fireworks"
    def __init__(self, cfg, videoCfg, sourceCfg, mosaicSplitDeltaFrames):
        self.cfg = cfg
        self.videoCfg = videoCfg
        self.mosaicSplitDeltaFrames = mosaicSplitDeltaFrames
        self.NUM_TILES_X = sourceCfg.width // cfg.tileW
        self.NUM_TILES_Y = sourceCfg.height // cfg.tileH
        maxStartFrame = (self.videoCfg.numFrames - mosaicSplitDeltaFrames)
        numCenters = random.randrange(10, 20)
        centers = [(random.randrange(self.NUM_TILES_X), random.randrange(self.NUM_TILES_Y)) for i in range(numCenters)]
        self.startFrame         = [[int(random.random() * maxStartFrame) for i in range(self.NUM_TILES_Y)] for j in range(self.NUM_TILES_X)]
        self.deltaAlphaPerFrame = [[1 / ((0.5 + 0.5 * random.random()) * mosaicSplitDeltaFrames) for i in range(self.NUM_TILES_Y)] for j in range(self.NUM_TILES_X)]

        for (cx, cy) in centers:
            self.startFrame[cx][cy] = random.randrange(maxStartFrame) # // 3, maxStartFrame // 2)

        for tile_x in range(self.NUM_TILES_X):
            for tile_y in range(self.NUM_TILES_Y):
                def distToCenter(center):
                    (cx, cy) = center
                    return (tile_x - cx)**2 + (tile_y - cy)**2
                #(cx,cy) = min(centers, key=distToCenter)
                #distToClosestCenter = int(math.sqrt((cx - tile_x)**2 + (cy - tile_y)**2))
                self.startFrame[tile_x][tile_y] = min(self.startFrame[cx][cy] + int(2 * math.sqrt((cx - tile_x)**2 + (cy - tile_y)**2)) for (cx, cy) in centers)
                self.deltaAlphaPerFrame[tile_x][tile_y] = 1 / (0.5 * mosaicSplitDeltaFrames)

def generateVideo(cfg, videoCfg, source, tiles, w=1024, h=768, videoFileName="mosaic-video.avi", FPS=25):
    # recombing closest and source tiles with complementary alpha values
    frameSize = (w, h)
    out = cv2.VideoWriter(videoFileName, cv2.VideoWriter_fourcc(*'DIVX'), FPS, frameSize)

    NUM_TILES_X = source.width // cfg.tileW
    mosaicSplitDeltaFrames = 40

    # alphaGen = WaveAlphaGenerator(cfg, videoCfg, source, mosaicSplitDeltaFrames)
    # alphaGen = RandomAlphaGenerator(cfg, videoCfg, source, mosaicSplitDeltaFrames)
    # alphaGen = FireworksAlphaGenerator(cfg, videoCfg, source, mosaicSplitDeltaFrames)
    alphaGen = videoCfg.alphaGenClass(cfg, videoCfg, source, mosaicSplitDeltaFrames)


    # building source tile array
    sourceTiles = {}
    for tile_x in range(NUM_TILES_X):
        x = tile_x * cfg.tileW
        for tile_y in range(source.height // cfg.tileH):
            y = tile_y * cfg.tileH
            local_thumb = source.data[y:(y+cfg.tileH), x:(x+cfg.tileW)]
            sourceTiles[(tile_x, tile_y)] = local_thumb

    for i in range(videoCfg.numFrames):
        # generating empty image for destination
        print(f"generating frame {i}")
        frame = np.zeros((source.height, source.width, 3), np.uint8)
        alphaGen.updateToFrame(i)
        for tile_x in range(NUM_TILES_X):
            x = tile_x * cfg.tileW
            for tile_y in range(source.height // cfg.tileH):
                alphaThumb = alphaGen.getAlpha(i, tile_x, tile_y)
                alphaSource = 1 - alphaThumb
                y = tile_y * cfg.tileH
                closest = tiles[(tile_x, tile_y)]
                local_thumb = sourceTiles[(tile_x, tile_y)]
                if alphaThumb == 0:
                    frame[y:(y+cfg.tileH), x:(x+cfg.tileW)] = local_thumb
                elif alphaThumb == 1.0:
                    frame[y:(y+cfg.tileH), x:(x+cfg.tileW)] = closest
                else:
                    frame[y:(y+cfg.tileH), x:(x+cfg.tileW)] = closest * alphaThumb + local_thumb * alphaSource
        img = cv2.resize(frame, frameSize)
        out.write(img)

    for j in range(videoCfg.extraFrames):
        out.write(img)

    out.release()


class PerfMetric:
    metricList = []

    def __init__(self, label):
        self.label = label
        self.startTS = None
        self.stopTS  = None
        PerfMetric.metricList.append(self)

    def start(self):
        self.startTS = time.perf_counter()
    def stop(self):
        self.stopTS = time.perf_counter()

    def summary(self):
        return f"{self.label:20} executed in {self.stopTS - self.startTS:.3} second(s)"

class Configuration:
    """ structure to store run configuration, including:
        - tile dimensions """
    def __init__(self, tileSize, imgDir, tileDir, minAlphaTile=0, maxAlphaTile=1):
        self.tileW, self.tileH = tileSize
        self.imgDir = imgDir
        self.tileDir = tileDir
        self.minAlphaTile = minAlphaTile
        self.maxAlphaTile = maxAlphaTile

class VideoConfiguration:
    """ Video-specific configuration """
    def __init__(self, numFrames, extraFrames, alphaGenLabel):
        self.numFrames = numFrames
        self.extraFrames = extraFrames
        self.alphaGenClass = AlphaGenerator.generators[alphaGenLabel]

class Source:
    """ structure to store source data and metadata """
    def __init__(self, sourceFilename):
        print("reading source image")
        self.data = cv2.imread(sourceFilename)
        self.sourceSize = (self.data.shape[1], self.data.shape[0])

    @property
    def width(self):
        return self.sourceSize[0]

    @property
    def height(self):
        return self.sourceSize[1]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='build the mosaic version of an image')
    parser.add_argument('--library', default=None, type=str, help='path to pixel library')
    parser.add_argument("--tile-dir", default="./.mosaic_libs/", type=str, help="directory to save pixel thumbnails")
    parser.add_argument('--source', type=str, help='path to source image')
    parser.add_argument('--fast', default=False, const=True, action="store_const", help="accelerate closest tile selection with fast and less accurate method")
    parser.add_argument('--metric', default=average_metric, type=parse_metric, help='set metric to determine closest thumbnail')
    parser.add_argument("--tile-size", default=(32, 32), type=parse_int_tuple, help='set thumbnail size')
    parser.add_argument("--random-size", default=6, type=int, help='size of the closest pixel set to chose from')
    parser.add_argument("--source-coeff", default=0.25, type=float, help='coefficient of source image in final output blending')
    parser.add_argument("--mosaic-coeff", default=0.75, type=float, help='coefficient of generated mosaic image in final output blending')
    parser.add_argument("--tile-angles", default=[0], type=(lambda s: [float(v) for v in s.split(",")]), help="list of possible angles for the tiles")
    parser.add_argument("--verbose", default=False, const=True, action="store_const", help="display more verbose info messages")
    parser.add_argument("--sampling", default=None, type=int, action="store", help="select a sample of the library (random)")
    parser.add_argument("--stripes", default=None, type=(lambda s: map(int, s.split(','))), action="store", help="optionally add stripes, option values is (width, step)")
    parser.add_argument("--min-alpha-tile", default=0, type=float, action="store", help="minimum alpha value for lib tile during composition")
    parser.add_argument("--max-alpha-tile", default=0, type=float, action="store", help="maximum alpha value for lib tile during composition")

    subParsers = parser.add_subparsers()
    def cmdLineVideoGen(args, cfg, source, tiles):
        frameW, frameH = args.size
        videoCfg = VideoConfiguration(args.num_frames, args.extra_frames, args.alpha_gen)
        generateVideo(cfg, videoCfg, source, tiles, frameW, frameH,
                      videoFileName=args.output)
    videoCmdParser = subParsers.add_parser('video', help='generate video output')
    videoCmdParser.add_argument("--size", default=(1024,768), type=(lambda s: map(int, s.split(','))), help="video frame size")
    videoCmdParser.add_argument("--num-frames", default=250,  type=int, help="number of video frames")
    videoCmdParser.add_argument("--extra-frames", default=250,  type=int, help="number of extra (still) frames")
    videoCmdParser.add_argument("--output", default="mosaic-video.avi",  type=str, help="filename for the output video")
    videoCmdParser.add_argument("--alpha-gen", default="random",  type=str, choices=AlphaGenerator.generators.keys(), help="filename for the output video")
    videoCmdParser.set_defaults(func=cmdLineVideoGen)

    def cmdLineSingleImgGen(args, cfg, source, tiles):
        dest = generateSingleImage(cfg, source, tiles, args.stripes) 
        cv2.imwrite(args.output, dest)
    imageCmdParser = subParsers.add_parser('image', help="generate image output")
    imageCmdParser.add_argument('--output', default="mosaic.png", type=str, help='path to destination image')
    imageCmdParser.set_defaults(func=cmdLineSingleImgGen)

    args = parser.parse_args()


    cfg = Configuration(args.tile_size,
                        args.library, args.tile_dir,
                        args.min_alpha_tile, args.max_alpha_tile)
    source = Source(args.source)

    print("building destination image of size {} x {}".format(source.width, source.height))

    # create performance metrics, they will be automatically added
    # in creation order to PerfMetric.metricList
    genLibMetric    = PerfMetric("tile lib      generation")
    genTilesMetric  = PerfMetric("closest tile  generation")
    genMosaicMetric = PerfMetric("mosaic output generation")

    print("loading image from library")
    genLibMetric.start()
    if args.library:
        image_library = build_image_library(cfg, args.metric, args.tile_angles, args.verbose, args.sampling)
    else:
        image_library = load_pixel_library(args.tile_dir, args.metric, args.tile_angles, args.verbose, args.sampling)
    genLibMetric.stop()


    print("building map of closest library tile for each source tile")
    genTilesMetric.start()
    tiles = buildMosaicTiles(source, args.metric, image_library, args.random_size, args.fast)
    genTilesMetric.stop()


    print("generating mosaic image/video")
    genMosaicMetric.start()
    args.func(args, cfg, source, tiles)
    genMosaicMetric.stop()


    for metric in PerfMetric.metricList:
        print(metric.summary())






