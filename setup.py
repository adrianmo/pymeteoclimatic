from setuptools import setup

setup(
    name='meteoclimatic',
    version='0.0.1',
    description='Meteoclimatic weather information',
    author='Adrián Moreno',
    url='https://github.com/adrianmo/pymeteoclimatic',
    packages=['meteoclimatic', ],
    install_requires=['lxml~=4.5',
                      'beautifulsoup4~=4.9'
                      ],
    license='MIT',
)
