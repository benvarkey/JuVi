from setuptools import setup
from setuptools.command.install import install
from distutils import log
import json
import os
import sys

kernel_json = {"argv":[sys.executable,"-m","virtuoso_kernel", "-f", "{connection_file}"],
 "display_name":"Virtuoso",
 "language":"skill",
 "codemirror_mode":"skill"
}

class install_with_kernelspec(install):
    def run(self):
        # Regular installation
        install.run(self)

        # Now write the kernelspec
        from jupyter_client.kernelspec import install_kernel_spec
        from IPython.utils.tempdir import TemporaryDirectory
        with TemporaryDirectory() as td:
            os.chmod(td, 0o755) # Starts off as 700, not user readable
            with open(os.path.join(td, 'kernel.json'), 'w') as f:
                json.dump(kernel_json, f, sort_keys=True)
            # TODO: Copy resources once they're specified

            log.info('Installing Virtuoso kernel spec')
            install_kernel_spec(td, 'virtuoso', user=self.user, replace=True)

#with open('README.rst') as f:
#    readme = f.read()

svem_flag = '--single-version-externally-managed'
if svem_flag in sys.argv:
    sys.argv.remove(svem_flag)

setup(name='virtuoso_kernel',
      version='0.3',
      description='A virtuoso kernel for IPython',
      #long_description=readme,
      author='Ben Varkey Benjamin',
      author_email='benvarkey@gmail.com',
      #url='',
      packages=['virtuoso_kernel'],
      cmdclass={'install': install_with_kernelspec},
      install_requires=['colorama>=0.3.3'],
      classifiers = [
          'Framework :: IPython',
          'License :: OSI Approved :: Apache Software License',
          'Programming Language :: Python :: 2.7',
          'Topic :: System :: Shells',
      ]
)
