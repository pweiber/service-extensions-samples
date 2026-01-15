from setuptools import setup, find_packages

setup(
    name='protodef',  # Or a more descriptive name for your generated protos
    version='1.0.0',
    # 'find_packages()' will look for all packages (directories with __init__.py)
    # in the current directory (which is 'protodef' when setup.py is run)
    # and its subdirectories.
    packages=find_packages(),
    # You might also want to specify that these packages don't have to be in a zip archive
    zip_safe=False,
    # If your .proto files generate non-Python files that need to be included,
    # you might need include_package_data=True and a MANIFEST.in file,
    # but for pure Python gRPC stubs, find_packages() is usually enough.
)