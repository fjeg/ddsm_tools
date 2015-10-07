import csv

__author__ = 'fgimenez'
import luigi
import os
from ddsm_util import get_abnormality_data, get_ics_info
from ddsm_classes import ddsm_abnormality


class DDSMCSV(luigi.Task):
    data_dir = luigi.Parameter()  # string of dir where all the data is
    output_dir = luigi.Parameter()  # string of dir where we want this output
    output_name = luigi.Parameter()  # name of the csv file

    def requires(self):
        pass

    def output(self):
        """
        output of CSV of all data
        """
        path = os.path.join(self.output_dir, self.output_name)
        return luigi.LocalTarget(path)

    def run(self):
        abnormalities = []

        for curdir, dirs, files in os.walk(self.data_dir):
            overlays = []
            ics_file_path = None
            for f in files:
                if f.endswith('.OVERLAY'):
                    overlays.append(os.path.join(self.data_dir, curdir, f))
                elif f.endswith('.ics'):
                    # ics is tuple of (full_file_path,file_name)
                    ics_file_path = os.path.join(self.data_dir, curdir, f)

            if not ics_file_path:
                continue

            ics_dict = get_ics_info(ics_file_path)
            for overlay_path in overlays:

                abnormality_data = get_abnormality_data(overlay_path)

                for file_name, lesion_type, lesion_data in abnormality_data:
                    abnormalities.append(ddsm_abnormality(file_name,
                                                          lesion_type,
                                                          lesion_data,
                                                          ics_dict))

        with open(self.output_name, 'w') as outfile:
            outfile_writer = csv.writer(outfile, delimiter=',')
            outfile_writer.writerow([getattr(abnormality, f) for f in fields])


if __name__ == '__main__':
    luigi.run(main_task_cls=DDSMCSV)
