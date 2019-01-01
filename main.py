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
		"palette": palette_metric
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


def build_image_library(original_library, metric_fct, dump_dir):
	if not os.path.isdir(dump_dir):
		print("creating directory {}".format(dump_dir))
		os.mkdir(dump_dir)
	image_library = []
	pixel_library = [f for f in os.listdir(dump_dir) if isfile(join(dump_dir, f))]
	for filename in [f for f in os.listdir(original_library) if isfile(join(original_library, f))]:
		print("processing {}".format(filename))
		base = os.path.basename(filename)
		prefix, extension = os.path.splitext(filename)
		thumb_filename = prefix + "_{}x{}".format(THUMB_W, THUMB_H) + extension
		if extension.lower() in [".png", ".jpg"]:
			if thumb_filename in pixel_library:
				print("pixel found in temporary library")
				thumb = cv2.imread(join(dump_dir, thumb_filename))
			else:
				print("pixel NOT found in temporary library")
				picture = cv2.imread(join(original_library, filename))
				thumb = cv2.resize(picture, (THUMB_W, THUMB_H))
			#average = thumb.mean(axis=0).mean(axis=0)
			metric = metric_fct(thumb)
			cv2.imwrite(os.path.join(dump_dir, thumb_filename), thumb)
			image_library.append((metric, thumb))
	return image_library


def build_mosaic(metric_fct, image_library, random_size=6):
	for tile_y in range(source_heigth / THUMB_H):
		for tile_x in range(source_width / THUMB_W):
			print("tile: {}, {}".format(tile_x, tile_y))
			x = tile_x * THUMB_W
			y = tile_y * THUMB_H
			local_thumb = source[y:(y+THUMB_H), x:(x+THUMB_W)]
			src_average = metric_fct(local_thumb)
			def dist(lib_img):
				delta = src_average - lib_img[0]
				return math.sqrt(delta.dot(delta))
			closest = sorted(image_library, key=dist)[random.randrange(random_size)][1]
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

	args = parser.parse_args()

	THUMB_W, THUMB_H = args.thumb_size

	print("reading source image")
	source = cv2.imread(args.source)
	source_width = source.shape[1]
	source_heigth = source.shape[0]

	print("building destination image of size {} x {}".format(source_width, source_heigth))
	dest = np.zeros((source_heigth, source_width, 3), np.uint8)
	print("loading image from library")

	image_library = build_image_library(args.library, args.metric, args.pixel_dir)
	build_mosaic(args.metric, image_library, args.random_size)
	cv2.imwrite(args.dest, dest)
			


			


