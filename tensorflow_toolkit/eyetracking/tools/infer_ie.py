#!/usr/bin/env python3
#
# Copyright (C) 2019 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions
# and limitations under the License.

from __future__ import print_function
from argparse import ArgumentParser
import logging as log
import sys
import os
import cv2
from openvino.inference_engine import IENetwork, IEPlugin
from tfutils.helpers import load_module

import time


def build_argparser():
  parser = ArgumentParser()
  parser.add_argument("--model", help="Path to an .xml file with a trained model.", required=True, type=str)
  parser.add_argument("--cpu_extension",
                      help="MKLDNN (CPU)-targeted custom layers. "
                           "Absolute path to a shared library with the kernels implementation", type=str, default=None)
  parser.add_argument("--plugin_dir", help="Path to a plugin folder", type=str, default=None)
  parser.add_argument("--device",
                      help="Specify the target device to infer on; CPU, GPU, FPGA or MYRIAD is acceptable. Sample "
                           "will look for a suitable plugin for device specified (CPU by default)", default="CPU",
                      type=str)
  parser.add_argument('--config', help='Path to a config.py', required=True)
  parser.add_argument('input_image', help='near-eye image, png or jpg')
  return parser


def load_ir_model(model_xml, device, plugin_dir, cpu_extension):
  model_bin = os.path.splitext(model_xml)[0] + ".bin"

  # initialize plugin
  log.info("Initializing plugin for %s device...", device)
  plugin = IEPlugin(device=device, plugin_dirs=plugin_dir)
  if cpu_extension and 'CPU' in device:
    plugin.add_cpu_extension(cpu_extension)

  # read IR
  print("model_bin: ", model_bin)
  log.info("Reading IR...")
  net = IENetwork(model=model_xml, weights=model_bin)

  if "CPU" in device:
    supported_layers = plugin.get_supported_layers(net)
    not_supported_layers = [l for l in net.layers.keys() if l not in supported_layers]
    if not_supported_layers:
      log.error("Following layers are not supported by the plugin for specified device %s:\n %s",
                device, ', '.join(not_supported_layers))
      log.error("Please try to specify cpu extensions library path in sample's command line parameters using "
                "--cpu_extension command line argument")
      sys.exit(1)

  # input / output check
  print("len(net.inputs.keys()):  ", len(net.inputs.keys()))
  assert len(net.inputs.keys()) == 1, "Eyenet must have only single input"
  assert len(net.outputs) == 1, "Eyenet must have only single output topologies"

  input_blob = next(iter(net.inputs))
  out_blob = next(iter(net.outputs))
  log.info("Loading IR to the plugin...")
  exec_net = plugin.load(network=net)
  shape = net.inputs[input_blob].shape # pylint: disable=E1136
  del net

  return exec_net, plugin, input_blob, out_blob, shape


def main():
  log.basicConfig(format="[ %(levelname)s ] %(message)s", level=log.INFO, stream=sys.stdout)
  args = build_argparser().parse_args()
  cfg = load_module(args.config)
  exec_net, plugin, input_blob, out_blob, shape = load_ir_model(args.model, args.device,
                                                                args.plugin_dir, args.cpu_extension)
  n_batch, channels, height, width = shape


  image = cv2.imread(args.input_image, cv2.IMREAD_GRAYSCALE)
  img_to_display = image.copy()
  cv2.imshow('sample image',image)
  print("press key to run inference engine")
  cv2.waitKey(0) # waits until a key is pressed
  in_frame = cv2.resize(image, (width, height))
  print("in_frame shape", in_frame.shape)
  #in_frame = in_frame.transpose((2, 0, 1))  # Change data layout from HWC to CHW
  in_frame = in_frame.reshape((n_batch, channels, height, width))

  #start = time.time()
  #for i in range(10000):
  result = exec_net.infer(inputs={input_blob: in_frame})
  #end = time.time()
  #print("elapsed time is ms: ", (end - start)/10)
  gazeX_out = result[out_blob][0]
  gazeY_out = result[out_blob][1]
  print("gazeX, gazeY out: ")
  print(gazeX_out, gazeY_out)

  del exec_net
  del plugin


if __name__ == '__main__':
  sys.exit(main() or 0)
