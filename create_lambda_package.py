# There is not a nice way to create a python lambda package on windows
# The provided Go tool does not seem to work with multiple files and the
# powershell built in Compress-Archive has a problem with including the root folder name
# therefore for a cross compatible way we'll use python to create
# the package.

import os
import os.path
import zipfile

def zip_dir(path, ziph):
    for root, dirs, files in os.walk(path):
        for file in files:
            ziph.write(os.path.join(root, file), 
                       arcname=os.path.relpath(os.path.join(root, file), path))

def zip_file(path, ziph):
    ziph.write(path)

zipf = zipfile.ZipFile('main.zip', 'w', zipfile.ZIP_DEFLATED)
zip_dir('package', zipf)
for python_file in [f for f in os.listdir('.') if os.path.isfile(f) and f.endswith('.py')]:
    zip_file(python_file, zipf)
zipf.close()