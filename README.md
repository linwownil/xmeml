## XMEML file generator

Automated XMEML file generation for video editing software. Currently, generated XMEML files are confirmed to be compatible with Adobe Premiere Pro (version 23.5.0)

### Features

- Saving sequence to XMEML file
	- subtitle track
	- audio track 
- Editable subtitles: populated text saved as `GraphicAndType` media type (Used by *Text Tool* in PPro)
- Subtitle parsing from SRT files
- Add audio file to the audio track
- Setting selected parameters:
    - frames per second
    - text position
    - audio level
    - manually defined non-ASCII text encoding
- Multiple XMEML generation tasks: Defined for one editing project in the configuration file

### Installation

This script requires Python 3.6+ and a `ffmpeg` installation.
Follow the instructions provided [here](http://ffmpeg.org/download.html) to install `ffmpeg` in your operating system. The system package manager may also provide this dependency.

Run the following commands:
 
    git clone https://github.com/linwownil/xmeml
    pip install -r requirements.txt

### Usage

1. Create a template sequence in PPro with desired subtitle style
2. Export the sequence: click *Files --> Export --> Final Cut Pro XML* and save the XML file
3. Inspect the saved XML and extract the subtitle style + parameters. Refer to the `template` XML files and `config-template.json`
4. Make a copy of `config-template.json` and name it `config.json`. Setup the configuration file with values extracted in last step
5. Run the script: `python xmeml.py`. The XMEML file will be saved in the project directory
6. Open PPro, load a PPro Project and drag the XMEML file into the project panel

### Contribution

PRs are welcome!

### License

xmeml is licenced under [MIT](https://opensource.org/license/mit/)