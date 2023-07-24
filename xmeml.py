import sys
import base64
import re
import xml.etree.ElementTree as ET
if sys.version_info < (3,9,0):
    from xml.dom import minidom
import copy
import os
import srt
import json
from math import floor, log10
import ffmpeg
import uuid

def re_match(pattern, string, m_index):
    iter = pattern.finditer(string)
    obj = next(x for i, x in enumerate(iter) if i==m_index)
    span = obj.span()

    return (obj, span)

def extract_sub(value):
    re_pattern = re.compile(r"\/\/\/\/")
    re_obj, re_span = re_match(re_pattern, value, 1)
    
    value_prefix = value[:re_span[1]]
    value_sub = value[re_span[1]:]
    
    return (value_prefix, value_sub)

def replace_sub(template_sub, sub, nonascii):
    #template value --> base64 decoded bytes
    input_byte = template_sub.encode("UTF-8")
    d_input_byte = base64.b64decode(input_byte)
    input_string_byte = str(d_input_byte)[2:-1]

    #subtitle --> bytes
    sub_byte = sub.encode("UTF-8")
    sub_byte_len_hex = f"\\x{len(sub_byte):02x}"
    sub_byte_str = str(sub_byte)[2:-1]
    
    #extract replace positions
    re_pattern = re.compile(r"(?<=\\x00\\x00\\x00).+?(?=\\x00\\x00\\x00)")
    re_cksobj, re_cksspan = re_match(re_pattern, input_string_byte, 3)
    re_subobj, re_subspan = re_match(re_pattern, input_string_byte, 4)

    #concatenate to output
    output_byte_str = ''.join((
        input_string_byte[:re_cksspan[0]],
        sub_byte_len_hex,
        input_string_byte[re_cksspan[0]+len(sub_byte_len_hex):re_cksspan[1]],
        input_string_byte[re_cksspan[1]:re_subspan[0]],
        sub_byte_str,
        input_string_byte[re_subspan[1]:]))

    #string with character-hex --> string with single escape
    output_byte = output_byte_str.encode("UTF-8")
    output_str = output_byte.decode('unicode_escape')
    #required to decode non-ascii characters
    if(nonascii["activate"]):
        output_byte = output_str.encode(nonascii["encoding"])
        #base64 encode string here
        output_byte = base64.b64encode(output_byte)
        output_str = output_byte.decode("UTF-8")
    
    return output_str

def time_to_frames(time, fps):
    # format: "HH:MM:SS.ssssss"
    factor = (60**2*fps, 60*fps, fps, fps/10**6)
    frames = []
    for t in time:
        l = re.split(r"[:.]", str(t))
        l = map(float, l)
        l = map(lambda x,y:x*y, l, factor)
        f = round(sum(l))
        frames.append(f)
    
    return frames

def add_subtitle_clipitem(t_id, sequence, config, clipitem_id):
    # load template
    t_clipitem_s_p = os.path.join(
        config["xml_template_path"],
        config["tasks"][t_id]["subtitle"]["_clipitem"])
    t_clipitem_s = ET.parse(t_clipitem_s_p)

    # parse srt file
    srt_p = os.path.join(config["project_path"], config["tasks"][t_id]["subtitle"]["srt"])
    with open(srt_p, "r", encoding="utf-8") as f:
        srt_f = f.read()
    srt_d = srt.parse(srt_f)
    
    # reformat srt data
    # format: [(string, start, end), ...]
    new_srt_d = []
    for sub in srt_d:
        # SubtitleEdit output always ends with [，.]
        c = sub.content[:-1]
        f_s, f_e = time_to_frames((sub.start, sub.end), config["tasks"][t_id]["_sequence"]["fps"])
        new_srt_d.append((c,f_s,f_e))
    
    video_track = sequence.find(".//video/track")
    
    for isub, sub in enumerate(new_srt_d):
        c = copy.deepcopy(t_clipitem_s)
        
        # clipitem id attribute, name node in clipitem + effect
        c.getroot().set("id", f"clipitem-{isub}")
        c.find("./name").text = sub[0]
        c.find(".//effect/name").text = sub[0]
        
        # time
        l = ["./start", "./end"]
        l = map(lambda n:c.find(n), l)
        for i, node in enumerate(l):
            if i < 1: node.text = str(sub[1])
            else: node.text = str(sub[2])
        
        # hash
        hash = str(uuid.uuid4())
        c_hash = c.find(".//parameter/hash")
        c_hash.text = hash
        
        # text
        c_text = c.find(".//parameter/[hash]").find("./value")
        t_text = config["tasks"][t_id]["subtitle"]["t_value"]
        t_prefix, t_sub = extract_sub(t_text)
        sub_new = replace_sub(t_sub, sub[0], config["tasks"][t_id]["subtitle"]["non_ascii"])
        c_text.text = ''.join((t_prefix, sub_new))

        # position
        t_pos = config["tasks"][t_id]["subtitle"]["t_position"]
        c_pos = c.find(".//parameter/[parameterid='3']").find("./value")
        pos_str = c_pos.text.split(",")
        pos_str[1] = f"{t_pos[0]}:{t_pos[1]}"
        pos_str = ','.join(pos_str)
        c_pos.text = pos_str
        
        # add to video track
        video_track.append(c.getroot())
        clipitem_id += 1
    
    return clipitem_id

def add_audio_clipitem(t_id, sequence, config, clipitem_id):
    # load template
    t_clipitem_a_p = os.path.join(
        config["xml_template_path"],
        config["tasks"][t_id]["audio"]["_clipitem"])
    t_clipitem_a = ET.parse(t_clipitem_a_p)

    c = copy.deepcopy(t_clipitem_a)
    
    # clipitem id attribute, name node in clipitem + file
    c.getroot().set("id", f"clipitem-{clipitem_id}")
    c.find("./name").text = config["tasks"][t_id]["audio"]["file"]
    c.find("./file/name").text = config["tasks"][t_id]["audio"]["file"]
    
    # construct audio uri
    a_path = re.sub(r'\\', r"/", config["project_path"])
    a_path = re.sub(r':', r"%3a", a_path)
    a_url_l= ["file:/", "localhost", a_path, config["tasks"][t_id]["audio"]["file"]]
    a_url = "/".join(a_url_l)
    # pathuri node
    c_pathuri = c.find(".//file/pathurl")
    c_pathuri.text = a_url
    
    # audio frames
    audio_p = os.path.join(config["project_path"], config["tasks"][t_id]["audio"]["file"])
    audio_end = ffmpeg.probe(audio_p, sexagesimal=None)["format"]["duration"]
    f_s, f_e = time_to_frames(("00.00.00:000000", audio_end), config["tasks"][t_id]["_sequence"]["fps"])
    c_start = c.find("./start")
    c_start.text = str(f_s)
    c_end = c.find("./end")
    c_end.text = str(f_e)
    
    # audio level
    # expressed as root-power quantity: L_F = 20*log_10(F/F_0) [db]
    # value accepts F/F_0 ratio, rounded to 6 significant figures
    level = 10 ** (config["tasks"][t_id]["audio"]["level"] / 20)
    round_to_n = lambda x, n: x if x == 0 else round(x, -int(floor(log10(abs(x)))) + (n - 1))
    level = str(round_to_n(level, 6))
    c_value = c.find(".//parameter/[parameterid='level']").find("value")
    c_value.text = level
    
    # add to audio track
    audio_track = sequence.find(".//audio/track")
    audio_track.append(c.getroot())
    clipitem_id += 1
    
    return clipitem_id

if __name__ == "__main__":
    # parse config file
    config_fn = "config.json"
    with open(config_fn, "r", encoding='UTF-8') as f:
        config = json.load(f)
    
    # run tasks
    for t_id, t in enumerate(config["tasks"]):
        clipitem_id = 0    
        
        # load sequence templates
        t_sequence_p = os.path.join(
            config["xml_template_path"],
            config["tasks"][t_id]["_sequence"]["file"])
        t_sequence = ET.parse(t_sequence_p)
    
        # create work copy of sequence
        sequence = copy.deepcopy(t_sequence)
        s_name = f"sequence-{t_id}"
        
        # generate clipitems for video track
        if "subtitle" in t:
            clipitem_id = add_subtitle_clipitem(t_id, sequence, config, clipitem_id)
            s_name = f"{s_name}-subtitle"
        # generate clipitems for audio track    
        if "audio" in t:
            clipitem_id = add_audio_clipitem(t_id, sequence, config, clipitem_id)
            s_name = f"{s_name}-audio"
        
        # add sequence name
        sequence_name = sequence.find(".//sequence/name")
        sequence_name.text = s_name
        
        # save xml to file
        output_p = os.path.join(config["project_path"], config["tasks"][t_id]["output"])
        with open(output_p, "w", encoding="UTF-8") as f:
            header = '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n'
            if sys.version_info >= (3,9,0):
                ET.indent(sequence, '  ')
            xml_string = ET.tostring(sequence.getroot()).decode("UTF-8")
            if sys.version_info < (3,9,0):
                xml_string = minidom.parseString(xml_string).toprettyxml(indent="  ")
                xml_string = xml_string.split('\n', 1)[1]
                xml_string = filter(lambda x: len(x.strip()), xml_string.split('\n'))
                xml_string = '\n'.join(xml_string)
            f.write(f"{header}{xml_string}")
