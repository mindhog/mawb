from distutils.core import setup, Extension

setup(
    ext_modules = [
        Extension("_alsa_midi", sources = ['alsa_midi.i'],
                  libraries = ['asound'],
                  )
    ],
    py_modules = ['alsa_midi'],
    install_requires = [
        'typing', # typing-3.6.6
    ],

    tests_require = [
        'mock', # mock-2.0.0
    ],
)