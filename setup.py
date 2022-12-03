from setuptools import setup

requirements = '''
    inotify_simple
'''

console_scripts = '''
    vire=vire:main
'''

setup(
    name='vire',
    py_modules=['vire'],
    version='0.1',
    description='A viable reloader',
    url='https://github.com/danr/vire',
    author='Dan Rosén',
    author_email='danr42@gmail.com',
    python_requires='>=3.7',
    license='MIT',
    install_requires=requirements.split(),
    entry_points={'console_scripts': console_scripts.split()}
)
