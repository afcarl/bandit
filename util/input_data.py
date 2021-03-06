# Copyright 2015 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

"""Functions for downloading and reading MNIST data."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import gzip
import os

import tensorflow.python.platform

import numpy
from six.moves import urllib
from six.moves import xrange  # pylint: disable=redefined-builtin

SOURCE_URL = 'http://yann.lecun.com/exdb/mnist/'

import matplotlib.pyplot as plt
import numpy as np
from scipy.misc import imresize
from scipy.ndimage import zoom

from util.util_funcs import nhot, onehot


def maybe_download(filename, work_directory):
  """Download the data from Yann's website, unless it's already here."""
  if not os.path.exists(work_directory):
    os.mkdir(work_directory)
  filepath = os.path.join(work_directory, filename)
  if not os.path.exists(filepath):
    filepath, _ = urllib.request.urlretrieve(SOURCE_URL + filename, filepath)
    statinfo = os.stat(filepath)
    print('Successfully downloaded', filename, statinfo.st_size, 'bytes.')
  return filepath


def _read32(bytestream):
  dt = numpy.dtype(numpy.uint32).newbyteorder('>')
  return numpy.frombuffer(bytestream.read(4), dtype=dt)[0]


def extract_images(filename):
  """Extract the images into a 4D uint8 numpy array [index, y, x, depth]."""
  print('Extracting', filename)
  with gzip.open(filename) as bytestream:
    magic = _read32(bytestream)
    if magic != 2051:
      raise ValueError(
          'Invalid magic number %d in MNIST image file: %s' %
          (magic, filename))
    num_images = _read32(bytestream)
    rows = _read32(bytestream)
    cols = _read32(bytestream)
    buf = bytestream.read(rows * cols * num_images)
    data = numpy.frombuffer(buf, dtype=numpy.uint8)
    data = data.reshape(num_images, rows, cols, 1)
    return data


def dense_to_one_hot(labels_dense, num_classes=10):
  """Convert class labels from scalars to one-hot vectors."""
  num_labels = labels_dense.shape[0]
  index_offset = numpy.arange(num_labels) * num_classes
  labels_one_hot = numpy.zeros((num_labels, num_classes))
  labels_one_hot.flat[index_offset + labels_dense.ravel()] = 1
  return labels_one_hot


def extract_labels(filename, one_hot=False):
  """Extract the labels into a 1D uint8 numpy array [index]."""
  print('Extracting', filename)
  with gzip.open(filename) as bytestream:
    magic = _read32(bytestream)
    if magic != 2049:
      raise ValueError(
          'Invalid magic number %d in MNIST label file: %s' %
          (magic, filename))
    num_items = _read32(bytestream)
    buf = bytestream.read(num_items)
    labels = numpy.frombuffer(buf, dtype=numpy.uint8)
    if one_hot:
      return dense_to_one_hot(labels)
    return labels

class MNISTDataSet(object):
    bsz = 16
    width = 45
    height = 45
    num_a = 3
    num_actions = 10
    mu = None
    std = None
    norm = False

class DataSet(MNISTDataSet):

  def __init__(self, images, labels, fake_data=False, one_hot=False):
    """Construct a DataSet.

    one_hot arg is used only if fake_data is true.  `dtype` can be either
    `uint8` to leave the input as `[0, 255]`, or `float32` to rescale into
    `[0, 1]`.
    """
    if fake_data:
      self._num_examples = 10000
      self.one_hot = one_hot
    else:
      assert images.shape[0] == labels.shape[0], (
          'images.shape: %s labels.shape: %s' % (images.shape,
                                                 labels.shape))
      self._num_examples = images.shape[0]

      # Convert shape from [num examples, rows, columns, depth]
      # to [num examples, rows*columns] (assuming depth == 1)
      assert images.shape[3] == 1
      images = images.reshape(images.shape[0],
                              images.shape[1] * images.shape[2])

      # Convert from [0, 255] -> [0.0, 1.0].
      images = images.astype(numpy.float32)
      if self.norm:
        print('hello')
        images -= self.mu
        images /= self.std
    self._images = images
    self._labels = labels
    self._epochs_completed = 0
    self._index_in_epoch = 0
    return

  @property
  def images(self):
    return self._images

  @property
  def labels(self):
    return self._labels

  @property
  def num_examples(self):
    return self._num_examples

  @property
  def epochs_completed(self):
    return self._epochs_completed

  def next_batch(self, batch_size = None, fake_data=False):
    """Return the next `batch_size` examples from this data set."""
    if batch_size is None:
      batch_size = self.bsz
    if fake_data:
      fake_image = [1] * 784
      if self.one_hot:
        fake_label = [1] + [0] * 9
      else:
        fake_label = 0
      return [fake_image for _ in xrange(batch_size)], [
          fake_label for _ in xrange(batch_size)]
    start = self._index_in_epoch
    self._index_in_epoch += batch_size
    if self._index_in_epoch > self._num_examples:
      # Finished epoch
      self._epochs_completed += 1
      # Shuffle the data
      perm = numpy.arange(self._num_examples)
      numpy.random.shuffle(perm)
      self._images = self._images[perm]
      self._labels = self._labels[perm]
      # Start next epoch
      start = 0
      self._index_in_epoch = batch_size
      assert batch_size <= self._num_examples
    end = self._index_in_epoch
    return self._images[start:end], self._labels[start:end]

  def random_policy(self, bsz=None):
      if bsz is None:
          bsz = self.bsz
      X, y = self.next_batch(batch_size =bsz)

      X = np.reshape(X,(bsz,28,28))

      # action = np.random.choice(self.num_actions, (self.bsz,))
      action = np.zeros((bsz,), dtype=np.int16)
      for i in range(bsz):
          H = 5
          p = H/(self.num_actions-1)*np.ones((self.num_actions,))
          p[y[i]] = H
          p /= self.num_actions
          action[i] = np.random.choice(self.num_actions, p=p)
      reward = np.clip(2-np.abs(action-y),0,5)
      return X[:,::2,::2], onehot(action), reward

  def plot_example(self,mix=False):
      """
      plots some examples of the data under consideration
      :param mix: plot examples from mixed or non-mixed dataset
      :return: None
      """
      if mix:
        im, label = self.next_mix_batch(False,bsz=4)
        width = im.shape[2]
        height = im.shape[1]
      else:
        im, label = self.next_batch(False,bsz=4)
        width = 28
        height = width

      f, axarr = plt.subplots(4,1)

      for x in range(4):
          axarr[x].imshow(np.reshape(im[x], (height,width)))
          axarr[x].set_title('label %s'%label[x])
      plt.show()
      return

  def simulate_logged_bandit(self, bsz = None):
      """Simulates the logged bandit feedback. For some features, it uses a random policy (to be defined) and
      calculates the corresponding reward"""
      if bsz is None:
        bsz = self.bsz

      IM, LBL = self.next_mix_batch()

      # Implement your random policy
      recommend = np.random.randint(0,self.num_actions,(bsz,))
      reward = np.zeros((bsz,))
      # TODO make this for-loop efficient
      for i in range(bsz):
          if recommend[i] in LBL[i]:
              reward[i] = 1

      return IM, onehot(recommend), reward





  def next_mix_batch(self,make_hot = False,bsz = None, width = None, height = None,NUM=None):
      """
      Samples a batch and mixes NUM digits into one big image
      :param bsz: batchsize of the output
      :param NUM: number of digits to mix
      :param make_hot: a function to make your output n_hot
      :return: image array [bsz, width, width] and label array [bsz,NUM]
      """
      #get fdefault arguments from class
      if bsz is None:
        bsz = self.bsz
      if width is None:
        width = self.width
      if NUM is None:
        NUM = self.num_a
      if height is None:
        height = self.height

      X,Y = self.next_batch(bsz*NUM)

      IM = [None]*bsz
      LBL = [None]*bsz

      width2 = 14

      # Randomly stack the image into the bigger image
      for b in range(bsz):
        im = np.zeros((height, width))
        vert = np.random.randint(0, max(int(width/3)-width2,1),(3,))
        hor = np.random.randint(0, height-width2, (3,))
        lbl = []
        for n in range(NUM):
          h = hor[n]
          v = min(vert[n]+width2*n,width-width2)

          i = b*NUM + n
          im_digit = zoom(np.reshape(X[i],(28,28)),0.5)
          im[h:h+width2,v:v+width2] = im_digit
          lbl.append(Y[i])
        IM[b] = im
        LBL[b] = np.array(lbl)

      IMS = np.stack(IM)
      LBLS = np.stack(LBL)


      if make_hot:
        return IMS, nhot(LBLS.copy()), LBLS
      else:
        return IMS, LBLS

def read_data_sets(train_dir, fake_data=False, one_hot=False,norm = True):
  data_sets = MNISTDataSet()

  if fake_data:
    def fake():
      return DataSet([], [], fake_data=True, one_hot=one_hot)
    data_sets.train = fake()
    data_sets.validation = fake()
    data_sets.test = fake()
    return data_sets

  TRAIN_IMAGES = 'train-images-idx3-ubyte.gz'
  TRAIN_LABELS = 'train-labels-idx1-ubyte.gz'
  TEST_IMAGES = 't10k-images-idx3-ubyte.gz'
  TEST_LABELS = 't10k-labels-idx1-ubyte.gz'
  VALIDATION_SIZE = 5000

  local_file = maybe_download(TRAIN_IMAGES, train_dir)
  train_images = extract_images(local_file)

  local_file = maybe_download(TRAIN_LABELS, train_dir)
  train_labels = extract_labels(local_file, one_hot=one_hot)

  local_file = maybe_download(TEST_IMAGES, train_dir)
  test_images = extract_images(local_file)

  local_file = maybe_download(TEST_LABELS, train_dir)
  test_labels = extract_labels(local_file, one_hot=one_hot)

  validation_images = train_images[:VALIDATION_SIZE]
  validation_labels = train_labels[:VALIDATION_SIZE]
  train_images = train_images[VALIDATION_SIZE:]
  train_labels = train_labels[VALIDATION_SIZE:]

  if norm:
    MNISTDataSet.mu = np.mean(train_images)
    MNISTDataSet.std = np.std(train_images)+1E-9
    MNISTDataSet.norm = True
  data_sets.train = DataSet(train_images, train_labels)
  data_sets.val = DataSet(validation_images, validation_labels)
  data_sets.test = DataSet(test_images, test_labels)

  return data_sets
