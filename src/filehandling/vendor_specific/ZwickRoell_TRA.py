# load measurement data from file
import filehandling.filehandling as fh 

def get_meta_dict(filepath):
    return(fh.csv_meta_to_dict(filepath,regex = "(\D* +) *(\d*\.*\d*) (.*)",max_header_lines = 100,encoding = "ISO-8859-1"))

def get_data_df(filepath):
    return(fh.csv_data_to_df(filepath,delimiter = ';'))
