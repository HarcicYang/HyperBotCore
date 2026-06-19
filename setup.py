from setuptools import setup, find_packages

import hyperot

setup(
    name="hyper-bot",
    provides=["hyperot"],
    version=hyperot.HYPER_BOT_VERSION,
    description="稳定高效、易于开发的QQ Bot框架",
    author="Harcic",
    author_email="harcic@outlook.com",
    url="https://github.com/HarcicYang/HypeR_Bot",
    packages=[
        "hyperot",
        "hyperot.adapters",
        "hyperot.LecAdapters",
        "hyperot.LecAdapters.OneBotLib",
        "hyperot.LecAdapters.MilkyLib",
        "hyperot.utils",
    ],
    # py_modules=["hytil"],
    install_requires=[
        "aiohttp~=3.9.5",
        "requests~=2.31.0",
        "httpx~=0.26.0",
        "websocket-client~=1.8.0",
        "Flask~=3.0.0",
        "ucfgr",
        "PyYAML"
    ],
    include_package_data=True
)
