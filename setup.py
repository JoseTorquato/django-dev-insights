from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="django-dev-insights",
    version="0.1.0",
    author="José Torquato",
    author_email="jltorquato12@gmail.com",
    include_package_data=True,
    description='Real-time performance insights for Django development.',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/josetorquato/django-dev-insights",
    license='MIT',
    packages=find_packages(exclude=["test_project*"]),
    install_requires=[
        "Django>=3.2",
        "colorama>=0.4.0",
    ],
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Framework :: Django :: 3.2',
        'Framework :: Django :: 4.0',
        'Framework :: Django :: 4.1',
        'Framework :: Django :: 4.2',
        'Framework :: Django :: 5.0',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    python_requires='>=3.8',
)
