import argparse
import cv2
import random
import math

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
    return img.mean(axis=0).mean(axis=0)

def palette_metric(img):
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



def build_image_library(original_library, metric_fct, dump_dir, tile_angles):
    if not os.path.isdir(dump_dir):
        print("creating directory {}".format(dump_dir))
        os.mkdir(dump_dir)
    image_library = []
    pixel_library = [f for f in os.listdir(dump_dir) if isfile(join(dump_dir, f))]
    for dirpath, dirnames, filenames in os.walk(original_library):
        for _f in filenames:
            filename = os.path.join(original_library, dirpath, _f)
            print("processing {}".format(filename))
            base = os.path.basename(filename)
            prefix, extension = os.path.splitext(base)
            thumb_filename = prefix + "_{}x{}".format(THUMB_W, THUMB_H) + extension
            if extension.lower() in [".png", ".jpg"]:
                if thumb_filename in pixel_library:
                    print("pixel found in temporary library")
                    thumb = cv2.imread(join(dump_dir, thumb_filename))
                else:
                    print("pixel NOT found in temporary library")
                    picture = cv2.imread(filename)
                    thumb = cv2.resize(picture, (THUMB_W, THUMB_H))
                    # saving thumbnail
                    cv2.imwrite(os.path.join(dump_dir, thumb_filename), thumb)
                for rot_angle in tile_angles:
                    M = cv2.getRotationMatrix2D((THUMB_W/2,THUMB_H/2),rot_angle,1)
                    new_tile = cv2.warpAffine(thumb,M,(THUMB_W,THUMB_H))
                    metric = metric_fct(new_tile)
                    image_library.append((metric, new_tile))
    print("{} image(s) library has been generated".format(len(image_library)))
    return image_library


def build_mosaic(metric_fct, image_library, random_size=6):
    for tile_y in range(source_heigth / THUMB_H):
        for tile_x in range(source_width / THUMB_W):
            x = tile_x * THUMB_W
            y = tile_y * THUMB_H
            local_thumb = source[y:(y+THUMB_H), x:(x+THUMB_W)]
            src_average = metric_fct(local_thumb)
            src_sub = sub_metric(local_thumb)
            def dist(lib_img):
                delta = src_average - lib_img[0]
                value = np.dot(delta, delta.transpose())
                return math.sqrt(value)
            def sub_dist(lib_img):
                delta = src_sub - sub_metric(lib_img[1])
                value = np.dot(delta, delta.transpose())
                return math.sqrt(value)
            closest_list = sorted(image_library, key=dist)[:random_size]
            #closest = random.choice(closest_list)[1]
            closest = sorted(closest_list, key=sub_dist)[random.randrange(random_size)][1]
            dest[y:(y+THUMB_H), x:(x+THUMB_W)] = closest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='build the mosaic version of an image')
    parser.add_argument('--library', type=str, help='path to pixel library')
    parser.add_argument("--pixel-dir", default="./.mosaic_libs/", type=str, help="directory to save pixel thumbnails")
    parser.add_argument('--source', type=str, help='path to source image')
    parser.add_argument('--dest', default="mosaic.png", type=str, help='path to destination image')
    parser.add_argument('--metric', default=average_metric, type=parse_metric, help='set metric to determine closest thumbnail')
    parser.add_argument("--thumb-size", default=(32, 32), type=parse_int_tuple, help='set thumbnail size')
    parser.add_argument("--random-size", default=6, type=int, help='size of the closest pixel set to chose from')
    parser.add_argument("--source-coeff", default=0.25, type=float, help='coefficient of source image in final output blending')
    parser.add_argument("--mosaic-coeff", default=0.75, type=float, help='coefficient of generated mosaic image in final output blending')
    parser.add_argument("--tile-angles", default=[0], type=(lambda s: [float(v) for v in s.split(",")]), help="list of possible angles for the tiles")

    args = parser.parse_args()

    THUMB_W, THUMB_H = args.thumb_size

    print("reading source image")
    source = cv2.imread(args.source)
    source_width = source.shape[1]
    source_heigth = source.shape[0]

    print("building destination image of size {} x {}".format(source_width, source_heigth))
    dest = np.zeros((source_heigth, source_width, 3), np.uint8)
    print("loading image from library")

    image_library = build_image_library(args.library, args.metric, args.pixel_dir, args.tile_angles)
    build_mosaic(args.metric, image_library, args.random_size)
    dest = cv2.addWeighted(source, args.source_coeff, dest, args.mosaic_coeff, 0)
    cv2.imwrite(args.dest, dest)






