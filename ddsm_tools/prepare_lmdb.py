import pandas as pd
import os
from subprocess import call
import numpy as np


def get_file_names(data_dir, descriptor, split=None, ext='.txt'):
    lmdb = os.path.join(data_dir, "{}_{}_lmdb{}".format(descriptor, split, ext))
    idx = os.path.join(data_dir, "{}_indices.txt".format(descriptor))
    return lmdb, idx


def make_train_val_test_splits(size, probs=(0.85, 0.05, 0.1)):
    """
    Make array of values {train, val, test} with distribution
    according to probs
    :param size: length of output array
    :param probs: (p_train, p_val, p_test)
    :return: list w/len size of train, val, test
    """
    assert np.sum(probs) == 1

    num_train = int(size * probs[0])
    num_val = int(size * probs[1])
    num_test = size - (num_train + num_val)

    splits = (['train'] * num_train)
    splits.extend(['val'] * num_val)
    splits.extend(['test'] * num_test)

    np.random.shuffle(splits)

    return splits


def make_lmdb_config_files(label, df, data_dir):
    """
    Create the csv files necessary to create lmdb for a label in the data frame.
    Takes care to split cases with multiple labels into their component pieces.
    :param label: which label to perform classification
    :param df: dataframe with all data
    :return: None
    """
    # make sure descriptor or path is null
    data = df[[label, 'od_crop_path']].dropna()

    # duplicate items with multiple annotations
    rows = []
    for idx, dname, im_path in data.itertuples():
        im_path = os.path.basename(im_path)
        rows.extend([(im_path, d) for d in dname.split('-')])

    # convert labels to numbers
    data = pd.DataFrame(rows, columns=['path', label])
    cat_desc = pd.Categorical(data[label])
    data[label] = cat_desc
    data['desc_codes'] = cat_desc.codes

    # make train/val/test splits
    data['splits'] = make_train_val_test_splits(len(data.index))

    # write out lmdb ref file
    for split in ['train', 'val', 'test']:
        # make output file paths
        lmdb_path, desc_idx_path = get_file_names(data_dir, label, split)
        split_data = data[data['splits'] == split]
        split_data.to_csv(lmdb_path,
                          columns=['path', 'desc_codes'],
                          sep=' ',
                          header=False,
                          index=False)

    # write out indices file
    _, desc_idx_path = get_file_names(data_dir, label)
    with open(desc_idx_path, 'w') as f:
        for idx, n in enumerate(cat_desc.categories):
            f.write("{}\t {}\n".format(n, idx))


def make_lmdb(data_dir,
              descriptor,
              tools_dir='/home/ubuntu/caffe/build/tools',
              resize_height=256,
              resize_width=256,
              img_dir='/home/ubuntu/processed_data_set/images/',
              lmdb_output_dir='/home/ubuntu/processed_data_set/lmdb/'):
    """
    Create the call string for the shell to make lmdb files
    then call it
    :param data_dir: directory with all data
    :param descriptor: name of descriptor to run
    :param params:
    :return:
    """

    for split in ['train', 'val', 'test']:
        lmdb_config_path, _ = get_file_names(data_dir, descriptor, split=split)
        lmdb_output_path, _ = get_file_names(lmdb_output_dir, descriptor, split=split, ext='')

        call_lst = ["GLOG_logtostderr=1",
                    os.path.join(tools_dir, 'convert_imageset'),
                    "--resize_height={}".format(resize_height),
                    "--resize_width={}".format(resize_width),
                    "--shuffle",
                    "--gray",
                    img_dir,
                    lmdb_config_path,
                    lmdb_output_path]

        call_str = " ".join(call_lst)
        print call_str
        call(call_str, shell=True)

        # make mean image of training data
        if split == 'train':
            mean_path = os.path.join(data_dir, 'mean_images', '{}_mean.binaryproto'.format(descriptor))
            call_lst = [os.path.join(tools_dir, 'compute_image_mean'),
                        lmdb_output_path,
                        mean_path]
            call_str = " ".join(call_lst)
            call(call_str, shell=True)

def make_data_sets(data_dir, data_csv_name):
    df = pd.read_csv(os.path.join(data_dir, data_csv_name))
    mass = df[df.abnormality_type == 'mass']  # get masses

    # make csv for lmdb creation
    make_lmdb_config_files('mass_margins', mass, data_dir)
    make_lmdb_config_files('mass_shape', mass, data_dir)

    # create lmdb files
    make_lmdb(data_dir, 'mass_margins')
    make_lmdb(data_dir, 'mass_shape')


if __name__ == '__main__':
    make_data_sets('/home/ubuntu/processed_data_set', 'ddsm_description_cases.csv')
