from setuptools import setup
from os import path

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='pymeteoclimatic',
    version='0.0.3',
    description='A Python wrapper around the Meteoclimatic service',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Adrián Moreno',
    author_email='adrian@morenomartinez.com',
    url='https://github.com/adrianmo/pymeteoclimatic',
    packages=['meteoclimatic', ],
    install_requires=['lxml~=4.5',
                      'beautifulsoup4~=4.9'
                      ],
    python_requires='>=3.6',
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries"],
    keywords='meteoclimatic client library api weather',
    license='MIT',
)
