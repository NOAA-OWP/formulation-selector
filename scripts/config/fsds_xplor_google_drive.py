
import os.path
from pathlib import Path


from pydrive2.drive import GoogleDrive
from pydrive2.auth import GoogleAuth
import warnings
import tempfile


#%% The pydrive approach


# TODO add config file
# Define the home dir
local_save_home_dir = ['temp','home_dir'][1]
if local_save_home_dir == 'temp':
    home_dir = str(tempfile.TemporaryDirectory())
elif local_save_home_dir == 'home_dir':
    home_dir = str(Path.home())
else:
    home_dir = local_save_home_dir

# The path containing client secrets
folder_with_client_secrets = f'{home_dir}/git/fsds/scripts/config/'

# The base dir for saving in google drive:
base_path_save_gdrive = "RegionalizationCollab/FSDS/temp_data/input/user_data_std/"
dir_save= f'{home_dir}/noaa/regionalization/data/input'# local save dir


# TODO acquire this from yaml config
path_data = f'{home_dir}/noaa/regionalization/data/julemai-xSSA/data_in/basin_metadata/basin_validation_results.txt'
name_data = os.path.basename(path_data)

# end config file input
#%% 
os.makedirs(dir_save, exist_ok = True)

def gdrive_auth_client_secrets(folder_with_client_secrets: str) -> pydrive2.drive.GoogleDrive:
    if any(x in folder_with_client_secrets for x in ['git','fsds','formulation-selector']):
        warnings.warn("Damn well be sure that all secrets files are in .gitignore if you're storing secrets in a git folder")
    
    if len( [x for x in Path(folder_with_client_secrets).glob('client_secrets.json')]) == 0:
        raise ValueError("User must manually save")

    # Requirement for GoogleAuth(): Change to the path where client_secrets.json lives!!
    os.chdir(folder_with_client_secrets)

    gauth = GoogleAuth()
    gauth.LocalWebserverAuth()
    drive = GoogleDrive(gauth)
    return drive

#%% pydrive download
# Identify file(s) of interest 
query = {'q': f"title = '{name_data}'"}
files = drive.ListFile(query).GetList()
# Download file(s)
saved_files = list()
for file_list in drive.ListFile(query):
  print('Received %s files from Files.list()' % len(file_list)) # <= 10
  for file1 in file_list:
      print('title: %s, id: %s' % (file1['title'], file1['id']))
      path_save_file = f"{dir_save}/{file1['title']}"
      saved_files.append(path_save_file)
      file1.GetContentFile(path_save_file) # Works!!
      print(f'Wrote file to: {path_save_file}')

#%% List subdirectories of interest
def _gdrive_lssubf(parent_folder_id: str, titles_to_match:list, indent=0) -> list:
    """ Generate list of google drive subfolder metadata corresponding to existing subfolder hierarchy

    :param parent_folder_id: the full filepath in google drive for existing subfolders
    :type parent_folder_id: str
    :param titles_to_match: An ordered list of subfolders in a google drive
    :type titles_to_match: list of str
    :param indent: _description_, defaults to 0
    :type indent: int, optional
    :return: list of pydrive2.files.GoogleDriveFile objects corresponding to each subfolder specifed in titles_to_match
    :rtype: list
    """
    query = f"'{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    folder_list = drive.ListFile({'q': query}).GetList()
    
    matches = []
    
    for folder in folder_list:
        if folder['title'] in titles_to_match:
            print(' ' * indent + f"Matched Title: {folder['title']}, ID: {folder['id']}")
            matches.append(folder)

        # Recursively list subfolders of the current folder and extend matches
        matches.extend(_gdrive_lssubf(folder['id'], titles_to_match, indent + 4))
    
    return matches

def wrap_gdrive_lssubf(gdrive_path: str, parent_folder_id = 'root') -> list:
    """ Wrapper that returns list of google drive hierarchical subfolder metadata

    :param gdrive_path: the path of 
    :type gdrive_path: str
    :param parent_folder_id: _description_, defaults to 'root'
    :type parent_folder_id: str, optional
    :raises warning: If the final subfolder's metadata does not match the requested final folder, then the full subfolder path doesn't exist in google drive
    :return: list of pydrive2.files.GoogleDriveFile objects corresponding to each subfolder specifed in titles_to_match
    :rtype: list
    """
    titles_to_match = gdrive_path.split('/')
    ls_id_all_sf = _gdrive_lssubf(parent_folder_id, titles_to_match)
    if ls_id_all_sf[-1]['title'] != titles_to_match[-1]:
        warnings.warn(f"Could not find the final google drive folder '{titles_to_match[-1]}'. Only found up to '{ls_id_all_sf[-1]['title']}'. Try creating the subfolder of interest")
    return ls_id_all_sf


ls_id_all_sf = wrap_gdrive_lssubf(base_path_save_gdrive)


#%% pydrive upload

# create a folder: https://developers.google.com/drive/api/guides/folder#create_a_folder

folder_metadata = {
    "title": "RegionalizationCollab/FSDS/temp_data/input/user_data_std/test_folder_pydrive2",
    # The mimetype defines this new file as a folder, so don't change this.
    "mimeType": "application/vnd.google-apps.folder",
}
folder = drive.CreateFile(folder_metadata)
folder.Upload()

def gdrive_create_subf(parent_folder_id, folder_name, drive: pydrive2.drive.GoogleDrive):
    folder_metadata = {
        'title': folder_name,
        'parents': [{'id': parent_folder_id}],
        'mimeType': 'application/vnd.google-apps.folder'
    }
    folder = drive.CreateFile(folder_metadata)
    folder.Upload()
    return folder

# TODO only create subfolders of those that are needed:


def wrap_gdrive_create_subf(base_path_save: str, path_data: str, drive: pydrive2.drive.GoogleDrive, ls_id_all_sf=None, ) -> list :
    """Create new hierarchical subfolders within existing google drive directories

    :param base_path_save: existing google drive subfolder directory structure
    :type base_path_save: str
    :param path_data: new google drive directory to be created
    :type path_data: str
    :param ls_id_all_sf: Optional list of google drive metadata for each subfolder as generated by wrap_gdrive_lssubf, defaults to None to simply generate this list
    :type ls_id_all_sf: list, optional
    :return: list of the google drive subfolder metadata pydrive2.files.GoogleDriveFile objects all the way down to the new folders just created
    :rtype: list
    """
    # Check to see if path_data includes a filename. If so, remove it to just the parent dirs
    if Path(path_data).suffix != '':
        path_data = Path(path_data).parent

    ls_subf_to_create = str(path_data).replace(str(base_path_save),'').split('/')

    if not ls_id_all_sf:
        # Get the existing ids by querying the existing google drive paths
        ls_id_all_sf = wrap_gdrive_lssubf(base_path_save)
    # Create the new subfolder(s)
    ctr = 0
    ls_new_folder_meta = list()
    for subf in ls_subf_to_create:
        if ctr == 0:
            parent_folder_id = ls_id_all_sf[-1]['id']
        new_folder = gdrive_create_subf(parent_folder_id,folder_name = subf, drive=drive)
        ctr += 1
        parent_folder_id = new_folder['id'] 
        ls_new_folder_meta.append(new_folder)

    new_ls_id_all_subf = ls_id_all_sf + ls_new_folder_meta    
    return new_ls_id_all_subf

# TODO define the save file path
path_data = Path(Path(base_path_save_gdrive)/Path("testit/testitagain"))

# Create any needed subfolders
new_ls_id_all_subf = wrap_gdrive_create_subf(base_path_save_gdrive, path_data, drive, ls_id_all_sf)


#%%

# Step 3: Specify the parent folder ID and subfolder name
parent_folder_id = 'your_parent_folder_id'  # Replace with the ID of the parent folder
subfolder_name = 'New Subfolder'  # Replace with the name of the subfolder you want to create

# Step 4: Create the subfolder within the parent folder
new_subfolder = create_subfolder(parent_folder_id, subfolder_name)


# TODO upload file


# Identify folder:
# TODO reference folderName
folderName = 'user_data_std'  # Please set the folder name.

folders = drive.ListFile(
    {'q': "title='" + folderName + "' and mimeType='application/vnd.google-apps.folder' and trashed=false"}).GetList()
for folder in folders:
    if folder['title'] == folderName:
        file2 = drive.CreateFile({'parents': [{'id': folder['id']}]})
        file2.SetContentFile('new_test.csv')
        file2.Upload()

#%% folder_i
# The sharing url for user_data_std
subdirid_user_data_std = 'https://drive.google.com/drive/folders/1kqIIEmVQvhSawEBXUzezzk-0IH-5awdk?usp=drive_link'

file1 = drive.CreateFile({'title': 'file.txt', 'parents': [{'id': subdirid_user_data_std}]})
file1.SetContentFile(path_save_file)
file1.Upload()

#%% Experimental from https://stackoverflow.com/questions/34101427/accessing-folders-subfolders-and-subfiles-using-pydrive-python

def parse_gdrive_path(gd_path):
    if ':' in gd_path:
        gd_path = gd_path.split(':')[1]
    gd_path = gd_path.replace('\\', '/').replace('//', '/')
    if gd_path.startswith('/'):
        gd_path = gd_path[1:]
    if gd_path.endswith('/'):
        gd_path = gd_path[:-1]
    return gd_path.split('/')

def resolve_path_to_id(folder_path,gdrive):
    _id = 'root'
    folder_path = parse_gdrive_path(folder_path)
    for idx, folder in enumerate(folder_path):
        folder_list = gdrive.ListFile({'q': f"'{_id}' in parents and title='{folder}' and trashed=false and mimeType='application/vnd.google-apps.folder'", 'fields': 'items(id, title, mimeType)'}).GetList()
        _id = folder_list[0]['id']
        title = folder_list[0]['title']
        if idx == (len(folder_path) - 1) and folder == title:
            return _id
    return _id



def get_folder_files(folder_ids, gdrive, batch_size=100):

    base_query = "'{target_id}' in parents"
    target_queries = []
    query = ''

    for idx, folder_id in enumerate(folder_ids):
        query += base_query.format(target_id=folder_id)
        if len(folder_ids) == 1 or idx > 0 and idx % batch_size == 0:
            target_queries.append(query)
            query = ''
        elif idx != len(folder_ids)-1:
            query += " or "
        else:
            target_queries.append(query)

    for query in target_queries:
        for f in gdrive.ListFile({'q': f"{query} and trashed=false", 'fields': 'items(id, title, mimeType, version)'}).GetList():
            yield f

def get_files(folder_path=None,gdrive = None, target_ids=None, files=[]):

    if target_ids is None:
        target_ids = [resolve_path_to_id(folder_path,gdrive)]

    file_list = get_folder_files(folder_ids=target_ids,gdrive=gdrive, batch_size=250)

    subfolder_ids = []

    for f in file_list:
        if f['mimeType'] == 'application/vnd.google-apps.folder':
            subfolder_ids.append(f['id'])
        else:
            files.append(f['title'])

    if len(subfolder_ids) > 0:
        get_files(target_ids=subfolder_ids)

    return files

file_list = get_files('RegionalizationCollab/FSDS/temp_data/input/user_data_std/',drive)






#%%
# Step 2: Function to recursively list subfolders
def list_subfolders(parent_folder_id, indent=0):
    query = f"'{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    folder_list = drive.ListFile({'q': query}).GetList()

    for folder in folder_list:

        print(' ' * indent + f"Title: {folder['title']}, ID: {folder['id']}")
        # Recursively list subfolders of the current folder
        list_subfolders(folder['id'], indent + 4)

# Step 3: Specify the parent folder ID and list subfolders
parent_folder_id = 'RegionalizationCollab'#'root'  # Replace with your parent folder ID
ls_dir_struct = "RegionalizationCollab/FSDS/temp_data/input/user_data_std".split('/')
list_subfolders(parent_folder_id,ls_dir_struct)



ls_dir_struct = "RegionalizationCollab/FSDS/temp_data/input/user_data_std/test_folder_pydrive2".split('/')


print("Subfolders listed successfully.")

#%%
