import argparse
import os

import keras
import keras.preprocessing.image

from keras_retinanet.models import ResNet50RetinaNet
from keras_retinanet.preprocessing import PascalVocIterator
import keras_retinanet

import tensorflow as tf


def get_session():
    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
    return tf.Session(config=config)


def create_model(weights='imagenet'):
    image = keras.layers.Input((None, None, 3))
    return ResNet50RetinaNet(image, num_classes=20, weights=weights)


def parse_args():
    parser = argparse.ArgumentParser(description='Simple training script for Pascal VOC object detection.')
    parser.add_argument('voc_path', help='Path to Pascal VOC directory (ie. /tmp/VOCdevkit/VOC2007).')
    parser.add_argument('--weights', help='Weights to use for initialization (defaults to ImageNet).', default='imagenet')
    parser.add_argument('--gpu', help='Id of the GPU to use (as reported by nvidia-smi).')

    return parser.parse_args()

if __name__ == '__main__':
    # parse arguments
    args = parse_args()

    # optionally choose specific GPU
    if args.gpu:
        os.environ['CUDA_VISIBLE_DEVICES'] = args.gpu
    keras.backend.tensorflow_backend.set_session(get_session())

    # create the model
    print('Creating model, this may take a second...')
    model = create_model(weights=args.weights)

    # compile model (note: set loss to None since loss is added inside layer)
    model.compile(
        loss={
            'regression'    : keras_retinanet.losses.smooth_l1(),
            'classification': keras_retinanet.losses.focal()
        },
        optimizer=keras.optimizers.adam(lr=1e-5, clipnorm=0.001)
    )

    # print model summary
    print(model.summary())

    # create image data generator objects
    train_image_data_generator = keras.preprocessing.image.ImageDataGenerator(
        rescale=1.0 / 255.0,
        horizontal_flip=True,
    )
    test_image_data_generator = keras.preprocessing.image.ImageDataGenerator(
        rescale=1.0 / 255.0,
    )

    # create a generator for training data
    train_generator = PascalVocIterator(
        args.voc_path,
        'trainval',
        train_image_data_generator
    )

    # create a generator for testing data
    test_generator = PascalVocIterator(
        args.voc_path,
        'test',
        test_image_data_generator
    )

    # start training
    batch_size = 1
    model.fit_generator(
        generator=train_generator,
        steps_per_epoch=len(train_generator.image_names) // batch_size,
        epochs=50,
        verbose=1,
        validation_data=test_generator,
        validation_steps=3000,  # len(test_generator.image_names) // batch_size,
        callbacks=[
            keras.callbacks.ModelCheckpoint('snapshots/resnet50_voc_best.h5', monitor='val_loss', verbose=1, save_best_only=True),
            keras.callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.1, patience=10, verbose=1, mode='auto', epsilon=0.0001, cooldown=0, min_lr=0),
        ],
    )

    # store final result too
    model.save('snapshots/resnet50_voc_final.h5')
