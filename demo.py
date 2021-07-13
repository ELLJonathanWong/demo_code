import streamlit as st
import numpy as np 
import cv2
import base64
from io import BytesIO
from PIL import Image
from pathlib import Path
import SessionState

# ------------------
# Overview
# Left Panel: 
# - Image Set Selection
# - Radio Button EV Minus Image/None
# - Focus Coordinate (text box)
# - Lens Simulation (text box)
# - Depth of Field (text box)
# - FStop (textbox) 
# - Image Format (textbox) 
# - Depth Format (textbox) 

# Right Display: 
# - Top Row: Primary Image, Depth Map
# - Bottom Row: EV, Processed Image
# EV image will display none if not provided. 
# Some text/table of metadata. 
# ---------------------

# Business Logic
@st.cache
def process(inputs: SessionState) -> Image:
  # inputs: data struct

  # Uploaded files must be read from PIL first, before converting to cv2.
  primary_img = convert_from_image_to_cv2(Image.open(inputs.primary_img_path))
  depth_img = convert_from_image_to_cv2(Image.open(inputs.depth_img_path))
  
  # Psuedo Processing 
  stacked_img = np.vstack([primary_img, depth_img])
  if inputs.ev_img_path != BLANK_PLACEHOLDER:
    ev_img = cv2.imread(str(inputs.ev_img_path))
    stacked_img = np.vstack([primary_img, depth_img, ev_img])
  stacked_img = increase_brightness(stacked_img, inputs.temporary_brightness)

  # Convert back to PIL-Streamlit standard. 
  stacked_img = convert_from_cv2_to_image(stacked_img)  
  return stacked_img

# Temporary 
def increase_brightness(img: np.ndarray, value: int) -> np.ndarray:
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
    h, s, v = cv2.split(hsv)

    lim = 255 - value
    v[v > lim] = 255
    v[v <= lim] += value

    final_hsv = cv2.merge((h, s, v))
    img = cv2.cvtColor(final_hsv, cv2.COLOR_HSV2RGB)
    return img

# Utils
def convert_from_cv2_to_image(img: np.ndarray) -> Image:
    return Image.fromarray(img)

def convert_from_image_to_cv2(img: Image) -> np.ndarray:
    return np.asarray(img)

def get_image_download_link(output_img: Image, filename: str, hyperlink_name: str) -> str: 
    buffered = BytesIO()
    output_img.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    href =  f'<a href="data:file/txt;base64,{img_str}" download="{filename}" style="float: right;">{hyperlink_name}</a>'
    return href

def record_test_case(inputs: SessionState, output: Image) -> None:
  # Make Folder 
  test_dir = Path.cwd() / 'tests'
  if not test_dir.exists():
    test_num = 0
  else:
    # Must read highest test number from disk to avoid race conditions.
    # This gets the highest number from disk in linear time, hopefully that's okay.
    test_num = max([int(path.stem.split('_')[1]) for path in Path('tests').iterdir()]) + 1
  test_case = test_dir / f'test_{test_num}'
  Path(test_case).mkdir(parents=True)

  # Write Parameters
  with open(test_case / 'parameters.txt', 'w') as f:
    text = f'''EV Image: {inputs.ev}
Focus Coordinates: {inputs.focus_coordinates}
Lens Simulation: {inputs.lens_simulation}
Depth of Field: {inputs.dof}
FStop: {inputs.fstop}
Image Format: {inputs.image_format}
Depth Format: {inputs.depth_format}'''
    f.write(text)

  # Write Images Locally, use aws sync to send to S3 bucket. 
  Image.open(inputs.primary_img_path).save(test_case / 'primary_image.jpg')
  Image.open(inputs.depth_img_path).save(test_case / 'depth_image.jpg')
  if inputs.ev_img_path != BLANK_PLACEHOLDER:
    Image.open(inputs.ev_img_path).save(test_case / 'ev_image.jpg')
  output.save(test_case / 'output.jpg')

# UI Scripting
# Initalization
# TODO: Replace with real image sets
st.set_page_config(layout='wide')
SAMPLE_IMAGES = {'Flatiron Image': {'primary': Path('images/flatiron.jpg'),
                             'depth': Path('images/flatiron.jpg'),
                             'ev': Path('images/flatiron.jpg')}, 
                 'Toucan Image': {'primary': Path('images/toucan.jpg'),
                             'depth': Path('images/toucan.jpg'),
                             'ev': Path('images/toucan.jpg')}} 
BLANK_PLACEHOLDER = Path('images/blank_image.png')
inputs = SessionState.get(pwd = '',
                        primary_img_path = BLANK_PLACEHOLDER,
                        depth_img_path = BLANK_PLACEHOLDER,
                        ev_img_path = BLANK_PLACEHOLDER,
                        user_upload = False,
                        ev = None, 
                        focus_coordinates = None,
                        lens_simulation = None, 
                        dof = None, 
                        fstop = None, 
                        image_format = None,
                        depth_format = None, 
                        temporary_brightness = 0)

def main() -> None: 
  # Inputs
  st.sidebar.title("Image Processing Demo")
  image_set = st.sidebar.selectbox('Image Set', list(SAMPLE_IMAGES.keys()) + ['Custom Images'])
  
  # Custom Input Images
  if image_set == "Custom Images": 
    # Reset Input Image Paths
    if inputs.user_upload is False:
      inputs.primary_img_path = BLANK_PLACEHOLDER
      inputs.depth_img_path = BLANK_PLACEHOLDER
      inputs.ev_img_path = BLANK_PLACEHOLDER

    # Image Form
    custom_image_widget = st.sidebar.form(key='image_form')
    with custom_image_widget:
      primary_temp = st.file_uploader("New Primary Image")
      depth_temp = st.file_uploader("New Depth Image")
      ev_temp = st.file_uploader("New EV Image (Optional)")
      image_submit_button = custom_image_widget.form_submit_button(label='Submit')

    # Save Image Paths
    if image_submit_button:
      # TODO: Add Type Check Input Verification to this if  
      if primary_temp is not None and depth_temp is not None:
        inputs.primary_img_path = primary_temp
        inputs.depth_img_path = depth_temp
        if ev_temp is not None: 
          inputs.ev_img_path = ev_temp
        inputs.user_upload = True  # Prevent reset after custom images uploaded
      else:
        st.sidebar.text('Please provide a primary and depth image.')
  
  # Otherwise, use sample images
  else:
    inputs.primary_img_path = SAMPLE_IMAGES[image_set]['primary']
    inputs.depth_img_path = SAMPLE_IMAGES[image_set]['depth']
    inputs.ev_img_path = SAMPLE_IMAGES[image_set]['ev']
    inputs.user_upload = False

  # Set Input Parameters, TODO: Add defaults
  form = st.sidebar.form(key='settings') 
  inputs.ev = form.radio('EV Image', ['Yes', 'No']) 
  inputs.focus_coordinates = form.text_input('Focus Coordinates')
  inputs.lens_simulation = form.text_input('Lens Simulation')
  inputs.dof = form.text_input('Depth of Field')
  inputs.fstop = form.text_input('FStop')
  inputs.image_format = form.text_input('Image Format')
  inputs.depth_format = form.text_input('Depth Format')
  inputs.temporary_brightness = form.slider('Temporary Brightness', 0, 50, 0)
  submit_button = form.form_submit_button(label='Submit')

  # Processing 
  primary_img = Image.open(inputs.primary_img_path).convert('RGB')
  depth_img = Image.open(inputs.depth_img_path).convert('RGB') 
  ev_img = Image.open(inputs.ev_img_path).convert('RGB')
  rendered_img = Image.open(BLANK_PLACEHOLDER).convert('RGB')
  if submit_button:
    rendered_img = process(inputs)

  # View
  primary_frame, depth_frame = st.beta_columns(2)
  ev_frame, rendered_frame = st.beta_columns(2)
  with primary_frame:
    st.subheader("Primary Image")
    st.image(primary_img)
  with depth_frame:
    st.subheader("Depth Map")
    st.image(depth_img)
  with ev_frame:
    st.subheader('EV Minus Image (Optional)')
    st.image(ev_img)  
  with rendered_frame:
    st.subheader('Rendered Image')
    st.image(rendered_img)

  # Client and Server Documentation
  if submit_button:
    # Client Download Link 
    img_file_name = 'rendered.jpg'
    st.markdown(get_image_download_link(rendered_img, img_file_name,'Download '+img_file_name), unsafe_allow_html=True)

    # Server Documentation
    record_test_case(inputs, rendered_img)

# Before entering main, perform user authentication
pwd = 'Leica_Labs'
if inputs.pwd != pwd:
  pwd_placeholder = st.sidebar.empty()
  user_pwd = pwd_placeholder.text_input("Password:", value="", type="password")
  inputs.pwd = pwd
  if inputs.pwd == pwd:
      pwd_placeholder.empty()
      main()
  elif inputs.pwd != '':
      st.text(inputs.pwd)
      st.error("Incorrect password. Please Try Again.")
else:
    main()

# NOTE:
# For setup, please install opencv and steamlit (that should be it for packages)
# For transfering files to S3, install awscli, then run aws configure, aws sync to transfer files to S3 bucket of choice.  


# push to git -> setup a new aws instance -> share to slack