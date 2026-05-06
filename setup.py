from setuptools import setup, find_packages

setup(
    name="npm-ghost",
    version="0.0.1",
    description="JS/Map NPM package recon tool — dependency confusion hunter",
    author="alonebeast002",
    license="MIT",
    python_requires=">=3.8",
    install_requires=[
        "chardet>=5.0.0",
        "brotli>=1.0.9",
    ],
    entry_points={
        "console_scripts": [
            "npm-ghost=npm_ghost.main:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Security",
    ],
    keywords="npm recon dependency-confusion bugbounty security",
)
