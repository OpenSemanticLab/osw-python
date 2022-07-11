import matplotlib.pyplot as plt
import os 


import filehandling.filehandling as fh 
import filehandling.vendor_specific.ZwickRoell_TRA as TRA
import plot_functions as plot_func

def main():
    folderpath = "test_data"
    print(os.listdir(folderpath))
    filenames = []
    for file in os.listdir(folderpath):
        if file.endswith("TRA"):
            filenames.append(file)
    
    filename = filenames[0] 
    filepath = folderpath+'/'+filename
    
    ### read data using general csv import 
    meta_dict,meta_dict_units = fh.csv_meta_to_dict(filepath,regex = "(\D* +) *(\d*\.*\d*) (.*)")
    
    ### read data using vendor specific import 
    meta_dict_2,meta_dict_units_2 = TRA.get_meta_dict(filepath)
    df =  TRA.get_data_df(filepath)
    print(meta_dict,df)
    
    
    
   # plot_force_length_diagram(filepath)
   # plot_time_diagram(filepath,mark_turning_points=True)
   # plot_falling_and_rising(filepath)
   # minima_change(filepath)
   
    plt.plot()
    plt.show()
                                  
    

if __name__ == '__main__':
    main()