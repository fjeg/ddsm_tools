import csv
import os

from ddsm_util import get_ics_info, get_abnormality_data
from ddsm_classes import ddsm_abnormality

fields = ['patient_id',
          'breast_density',
          'side',
          'view',
          'abn_num',
          'abnormality_type',
          'mass_shape',
          'mass_margins',
          'calc_type',
          'calc_distribution',
          'assessment',
          'pathology',
          'subtlety',
          'scanner_type',
          'scan_institution',
          'width',
          'height',
          'bpp',
          'resolution',
          'x_lo',
          'y_lo',
          'x_hi',
          'y_hi',
          'od_img_path',
          'od_crop_path',
          'mask_path']


def make_data_set(root, out_dir):
    outfile = open(os.path.join(out_dir, 'ddsm_description_cases.csv'), 'w')
    outfile_writer = csv.writer(outfile, delimiter=',')
    outfile_writer.writerow(fields)

    img_dir = os.path.join(out_dir, 'raw_images')
    crop_dir = os.path.join(out_dir, 'cropped_images')
    od_dir = os.path.join(out_dir, 'od_images')
    od_crop_dir = os.path.join(out_dir, 'od_cropped_images')
    mask_dir = os.path.join(out_dir, 'mask_images')

    for dir_path in [img_dir, crop_dir, od_dir, od_crop_dir, mask_dir]:
        if not os.path.exists(dir_path):
            os.mkdir(dir_path)

    count = 0
    for curdir, dirs, files in os.walk(root):
        overlays = []
        ics_file_path = None
        for f in files:
            if f.endswith('.OVERLAY'):
                overlays.append(os.path.join(root, curdir, f))
            elif f.endswith('.ics'):
                # ics is tuple of (full_file_path,file_name)
                ics_file_path = os.path.join(root, curdir, f)

        if not ics_file_path:
            continue

        ics_dict = get_ics_info(ics_file_path)
        for overlay_path in overlays:

            abnormality_data = get_abnormality_data(overlay_path)

            for file_name, lesion_type, lesion_data in abnormality_data:
                abnormality = ddsm_abnormality(file_name,
                                               lesion_type,
                                               lesion_data,
                                               ics_dict)

                count += 1
                if count % 100 == 0:
                    print "abnormality {}".format(count)

                try:
                    # raw gray-level
                    # abnormality.raw_img_path = abnormality.save_image(out_dir=img_dir)

                    # raw gray-level crops
                    # abnormality.raw_crop_path = abnormality.save_image(out_dir=crop_dir, crop=True)

                    # uint8 optical density
                    abnormality.od_img_path = abnormality.save_image(out_dir=od_dir, od_correct=True)

                    # uint8 optical density crops
                    abnormality.od_crop_path = abnormality.save_image(out_dir=od_crop_dir,
                                                                      od_correct=True,
                                                                      crop=True)
                    # resized od images
                    # d = os.path.join(out_dir, 'od_resized_crops')
                    # abnormality.save_image(out_dir=d, od_correct=True, crop=True, resize=(256, 256))

                    abnormality.mask_path = abnormality.save_mask(out_dir=mask_dir)

                except ValueError:
                    print "Error with abnormality at " + abnormality.input_file_path

                try:
                    outfile_writer.writerow([getattr(abnormality, f) for f in fields])
                except AttributeError:
                    print "Abnormality {} has no od image".format(abnormality.input_file_path)

    outfile.close()


if __name__ == '__main__':
    make_data_set('/Volumes/DDSM/DDSM/figment.csee.usf.edu/pub/DDSM/cases/',
                  out_dir='/Volumes/DDSM/ddsm_2015/processed_data_set')
