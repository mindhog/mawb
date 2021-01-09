from distutils.core import setup, Extension

setup(
    ext_modules = [
        Extension("_alsa_midi", sources = ['alsa_midi.i'],
                  libraries = ['asound'],
                  ),
        Extension("_lilv", sources = ['lilv.i'],
                  libraries = ['lilv-0'],
                  )
    ],
    py_modules = [
        'alsa_midi',
        'amidi',
        'lilv',
        'midi',
	'awb_client',
    ],
    install_requires = [
        'typing', # typing-3.6.6
    ],
    tests_require = [
        'mock', # mock-2.0.0
    ],
    scripts = [
        'isokbd.py',
        'midiedit.py',
    ],
)
