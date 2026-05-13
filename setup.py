import os
import setuptools

os.environ["PYTHONIOENCODING"] = "utf-8"

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="al-script",
    version="0.1.0",
    author="al-script contributors",
    description="Game automation framework extracted from Alas",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/al-script",
    packages=setuptools.find_packages(),
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
    ],
    install_requires=[
        "opencv-python>=4.5",
        "numpy>=1.21",
        "Pillow>=9.0",
        "scipy>=1.7",
        "scikit-image>=0.18",
        "pywin32>=306",
        "psutil>=5.8",
        "adb-shell>=0.4",
        "PySide6>=6.5",
        "requests>=2.28",
        "pyappify>=1.0.2",
    ],
    extras_require={
        "update": ["gitpython>=3.1"],
        "ocr": [
            "cnocr>=2.2",
            "paddleocr>=2.7",
        ],
        "dev": [
            "pytest>=7.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "al-script=module.launcher:main",
        ],
        "gui_scripts": [
            "al-script-gui=module.gui.launcher:main",
        ],
    },
    python_requires=">=3.10",
    zip_safe=False,
)
