from numpy import array, savetxt
import numpy as np
import os
from subprocess import call
from PIL import Image, ImageDraw

from ddsm_util import get_value


# hack because PIL doesn't like uint16
Image._fromarray_typemap[((1, 1), "<u2")] = ("I", "I;16")


class ddsm_abnormality(object):
    # index of data locations in overlay files
    idx = {
        'abn_num': 1,
        'shape': 3,
        'margins': 5,
        'assessment': 1,
        'pathology': 1,
        'chain': 7,
        'bound_x': (7, 0),
        'bound_y': (7, 1),
        'subtlety': 1,
        'calc_type': 3,
        'distribution': 5,
    }

    # hash mapping chain code to xy offsets
    chain_hash = {
        '0': (0, -1),
        '1': (1, -1),
        '2': (1, 0),
        '3': (1, 1),
        '4': (0, 1),
        '5': (-1, 1),
        '6': (-1, 0),
        '7': (-1, -1)
    }

    def __init__(self,
                 file_name,
                 abnormality_type,
                 data,
                 ics_dict):

        fname = os.path.basename(file_name)
        case_id, sequence, ext = fname.split('.')

        # file path data
        # input_file_path = {path to case dir}/{case name}
        self.input_file_path = file_name[:-1 * len('.OVERLAY')]

        # image information
        self.height = ics_dict[sequence]['height']
        self.width = ics_dict[sequence]['width']
        self.bpp = ics_dict[sequence]['bpp']
        self.resolution = ics_dict[sequence]['resolution']
        self.scanner_type = ics_dict['scanner_type']
        self.scan_institution = ics_dict['scan_institution']

        # patient information
        self.patient_id = ics_dict['patient_id']
        self.side, self.view = sequence.split('_')
        self.breast_density = ics_dict['density']

        # abnormality information
        self.abn_num = get_value(data, 'ABNORMALITY', self.idx['abn_num'])
        self.abnormality_type = abnormality_type
        self.assessment = get_value(data, 'ASSESSMENT', self.idx['assessment'])
        self.pathology = get_value(data, 'PATHOLOGY', self.idx['pathology'])
        self.subtlety = get_value(data, 'SUBTLETY', self.idx['subtlety'])

        # roi information
        self.roi = self._chaincode2roi(data)
        x = [xy[0] for xy in self.roi]
        y = [xy[1] for xy in self.roi]
        self.x_lo = min(x)
        self.x_hi = max(x)
        self.y_lo = min(y)
        self.y_hi = max(y)

        # calc/mass specific information
        self.calc_type = None
        self.calc_distribution = None
        self.mass_shape = None
        self.mass_margins = None

        if abnormality_type == 'mass':
            self.mass_shape = get_value(data, 'LESION_TYPE', self.idx['shape'])
            self.mass_margins = get_value(data, 'LESION_TYPE', self.idx['margins'])
        elif abnormality_type == 'calcification':
            self.calc_type = get_value(data, 'LESION_TYPE', self.idx['calc_type'])
            self.calc_distribution = get_value(data, 'LESION_TYPE', self.idx['distribution'])

        # image information
        self._raw_image = None

    ###################################################
    # ROI Methods
    ###################################################
    def write_roi(self):
        savetxt(self.input_file_path + '_ROI.csv', array(self.roi), fmt='%d', delimiter=',')

    def _chaincode2roi(self, lst):
        # chain code lookup table
        """
        code value        0     1     2     3     4     5     6     7
        X Coordinate    0     1     1     1     0    -1    -1    -1
        Y coordinate    -1    -1     0     1     1     1     0    -1
        """

        chain_idx = -1
        for idx, l in enumerate(lst):
            if l[0] == 'BOUNDARY':
                chain_idx = idx + 1
                break

        if chain_idx < 0:
            exit("ERROR WITH CHAIN CODE")

        x = int(lst[chain_idx][0])
        y = int(lst[chain_idx][1])
        chain = lst[chain_idx][2:]

        code = []
        code.append((x, y))
        prev_coord = (x, y)
        for c in chain:
            if c == '#':
                break
            d = self.chain_hash[c]
            new_coord = (prev_coord[0] + d[0], prev_coord[1] + d[1])
            code.append(new_coord)

            prev_coord = new_coord

        return code

    ###################################################
    # Image Methods
    ###################################################
    def _decompress_ljpeg(self, log_file_path='ljpeg_decompression_log.txt'):
        """
        :param im_path: base path for ljpeg
        :param log_file_path: path to log for writing these
        :return: None
        """
        with open(log_file_path, 'a') as log_file:
            ljpeg_path = self.input_file_path + '.LJPEG'
            if os.path.exists(ljpeg_path + '.1'):
                log_file.write("Decompressed LJPEG Exists: " + ljpeg_path)
            else:
                call_lst = ['./jpegdir/jpeg', '-d', '-s', ljpeg_path]
                call(call_lst, stdout=log_file)

        print "Decompressed {}".format(ljpeg_path)

    def _read_raw_image(self, force=False):
        """
        Read in a raw image into a numpy array
        :param force: boolean flag if we should force a read if we already have this image
        :return: None
        """

        # only read if we haven't already or
        # we aren't trying to force a read
        if (self._raw_image is not None) and not force:
            return

        # make sure decompressed image exists
        raw_im_path = self.input_file_path + '.LJPEG.1'
        if not os.path.exists(raw_im_path):
            self._decompress_ljpeg()

        # read it in and make it correct
        im = np.fromfile(raw_im_path, dtype=np.uint16)
        im.shape = (self.height, self.width)
        self._raw_image = im.byteswap()  # switch endian

    def _od_correct(self, im):
        """
        Map gray levels to optical density level
        :param im: image
        :return: optical density image
        """
        im_od = np.zeros_like(im, dtype=np.float64)

        if (self.scan_institution == 'MGH') and (self.scanner_type == 'DBA'):
            im_od = (np.log10(im + 1) - 4.80662) / -1.07553  # add 1 to keep from log(0)
        elif (self.scan_institution == 'MGH') and (self.scanner_type == 'HOWTEK'):
            im_od = (-0.00094568 * im) + 3.789
        elif (self.scan_institution == 'WFU') and (self.scanner_type == 'LUMISYS'):
            im_od = (im - 4096.99) / -1009.01
        elif (self.scan_institution == 'ISMD') and (self.scanner_type == 'HOWTEK'):
            im_od = (-0.00099055807612 * im) + 3.96604095240593
        return im_od

    # todo fix output paths
    def save_image(self,
                   out_dir=None,
                   out_name=None,
                   crop=False,
                   od_correct=False,
                   make_dtype=None,
                   resize=None,
                   force=False):
        """
        save the image data as a tiff file (without correction)
        :param out_dir: directory to put this image
        :param out_name: name of file to save image as
        :param crop: boolean to decide whether to crop lesion
        :param od_correct: boolean to decide to perform od_correction
        :param make_dtype: boolean to switch to 8-bit encoding
        :param force: force if this image already exists
        :return: path of the image
        """
        # construct image path
        if out_dir is None:
            out_dir = os.path.split(self.input_file_path)[0]

        if out_name is None:
            if crop:
                out_name = "{}_{}.tif".format(os.path.split(self.input_file_path)[1], self.abn_num)
            else:
                out_name = "{}.tif".format(os.path.split(self.input_file_path)[1])

        im_path = os.path.join(out_dir, out_name)

        # don't write if image exists and we aren't forcing it
        if os.path.exists(im_path) and not force:
            return im_path

        # make sure we have an image to save
        if self._raw_image is None:
            self._read_raw_image()

        im_array = np.copy(self._raw_image)

        # do appropriate image transformations
        # save resultant location for csv writing later
        if crop:
            im_array = im_array[self.y_lo:self.y_hi, self.x_lo:self.x_hi]

        # convert to optical density
        if od_correct:
            im_array = self._od_correct(im_array)
            im_array = np.interp(im_array, (0.0, 4.0), (255, 0))
            im_array = im_array.astype(np.uint8)

        if make_dtype == 'uint8':
            pass

        # create image object
        im = Image.fromarray(im_array)

        # resize if necessary
        if resize:
            im = im.resize(resize, resample=Image.LINEAR)

        # save image
        im.save(im_path, 'tiff')

        # return location of image
        return im_path

    # TODO save mask
    def save_mask(self, out_dir=None, out_name=None):
         # construct image path
        if out_dir is None:
            out_dir = os.path.split(self.input_file_path)[0]

        if out_name is None:
            out_name = "{}_{}.tif".format(os.path.split(self.input_file_path)[1], self.abn_num)

        im_path = os.path.join(out_dir, out_name)

        img = Image.new('L', (self.width, self.height), 0)
        ImageDraw.Draw(img).polygon(self.roi, outline=1, fill=1)
        img.save(im_path, 'tiff')

    ###################################################
    # Representation
    ###################################################
    def __str__(self):
        s = """
        Lesion: {0}
        Shape: {1}
        Margins: {2}
        Morphology: {3}
        Distribution: {4}
        Assessment: {5}
        Pathology: {6}
        File: {7}
        """.format(self.abnormality_type,
                   self.mass_shape,
                   self.mass_margins,
                   self.calc_type,
                   self.calc_distribution,
                   self.assessment,
                   self.pathology,
                   self.input_file_path)

        return s