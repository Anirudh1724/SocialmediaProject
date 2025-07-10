from setuptools import setup, find_packages

setup(
    name='Socialmedia',
    version='0.1.0',
    description='Unified SDK for Instagram, Pinterest, Quora, YouTube, Threads, and Twitter scraping',
    author='Anirudh Sai',
    packages=find_packages(),  # This finds all folders with __init__.py
    include_package_data=True,
    install_requires=[
        # Add dependencies like selenium, requests, etc.
    ],
    python_requires='>=3.7',
)

packages=find_packages()
