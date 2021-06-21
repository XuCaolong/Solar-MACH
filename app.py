import base64
import datetime
import io
import json
import os
import pickle
import re
import uuid

import astropy.units as u
import pandas as pd
import streamlit as st
from astropy.coordinates import SkyCoord
from sunpy.coordinates import frames

from backmapping import *

# set page config
st.set_page_config(page_title='Solar-MACH', page_icon=":satellite:", 
                   initial_sidebar_state="expanded")

st.title('Solar-MACH')
st.markdown('## Multi-spacecraft longitudinal configuration plotter')

# Define Download button, from https://discuss.streamlit.io/t/how-to-add-a-download-excel-csv-function-to-a-button/4474/9
def download_button(object_to_download, download_filename, button_text, pickle_it=False):
    """
    Generates a link to download the given object_to_download.

    Params:
    ------
    object_to_download:  The object to be downloaded.
    download_filename (str): filename and extension of file. e.g. mydata.csv,
    some_txt_output.txt download_link_text (str): Text to display for download
    link.
    button_text (str): Text to display on download button (e.g. 'click here to download file')
    pickle_it (bool): If True, pickle file.

    Returns:
    -------
    (str): the anchor tag to download object_to_download

    Examples:
    --------
    download_link(your_df, 'YOUR_DF.csv', 'Click to download data!')
    download_link(your_str, 'YOUR_STRING.txt', 'Click to download text!')

    """
    if pickle_it:
        try:
            object_to_download = pickle.dumps(object_to_download)
        except pickle.PicklingError as e:
            st.write(e)
            return None

    else:
        if isinstance(object_to_download, bytes):
            pass

        elif isinstance(object_to_download, pd.DataFrame):
            object_to_download = object_to_download.to_csv(index=False)

        # Try JSON encode for everything else
        else:
            object_to_download = json.dumps(object_to_download)

    try:
        # some strings <-> bytes conversions necessary here
        b64 = base64.b64encode(object_to_download.encode()).decode()

    except AttributeError as e:
        b64 = base64.b64encode(object_to_download).decode()

    button_uuid = str(uuid.uuid4()).replace('-', '')
    button_id = re.sub('\d+', '', button_uuid)

    custom_css = f""" 
        <style>
            #{button_id} {{
                background-color: rgb(255, 255, 255);
                color: rgb(38, 39, 48);
                padding: 0.25em 0.38em;
                position: relative;
                text-decoration: none;
                border-radius: 4px;
                border-width: 1px;
                border-style: solid;
                border-color: rgb(230, 234, 241);
                border-image: initial;

            }} 
            #{button_id}:hover {{
                border-color: rgb(246, 51, 102);
                color: rgb(246, 51, 102);
            }}
            #{button_id}:active {{
                box-shadow: none;
                background-color: rgb(246, 51, 102);
                color: white;
                }}
        </style> """

    dl_link = custom_css + f'<a download="{download_filename}" id="{button_id}" href="data:file/txt;base64,{b64}">{button_text}</a><br></br>'

    return dl_link


# provide date and time
with st.sidebar.beta_container():
    d = st.sidebar.date_input("Select date", datetime.date.today()-datetime.timedelta(days = 2))
    t = st.sidebar.time_input('Select time', datetime.time(1, 30))
    date = datetime.datetime.combine(d, t).strftime("%Y-%m-%d %H:%M:%S")

# plotting settings
with st.sidebar.beta_container():
    st.sidebar.subheader('Plot options:')
    plot_spirals = st.sidebar.checkbox('Parker spiral for each body', value=True)
    plot_sun_body_line = st.sidebar.checkbox('Straight line from Sun to body', value=True)
    show_earth_centered_coord = st.sidebar.checkbox('Add Earth-aligned coord. system', value=False)

    plot_reference = st.sidebar.checkbox('Plot reference (e.g. flare)', value=True)

    with st.sidebar.beta_expander("Reference coordinates (e.g. flare)", expanded=plot_reference):
        reference_sys = st.radio('Coordinate system:', ['Carrington', 'Stonyhurst'], index=0)
        if reference_sys == 'Carrington':
            reference_long = st.slider('Longitude:', 0, 360, 20)
            reference_lat = st.slider('Latitude:', -90, 90, 0)
        if reference_sys == 'Stonyhurst':
            reference_long = st.slider('Longitude:', -180, 180, 20)
            reference_lat = st.slider('Latitude:', -90, 90, 0)
            # convert Stonyhurst coordinates to Carrington for further use:
            coord = SkyCoord(reference_long*u.deg, reference_lat*u.deg, frame=frames.HeliographicStonyhurst, obstime=date)
            coord = coord.transform_to(frames.HeliographicCarrington(observer='Sun'))
            reference_long = coord.lon.value
            reference_lat = coord.lat.value
        import math
        reference_vsw = int(float(st.text_input('Solar wind speed for reference', 400)))
    if plot_reference is False:
        reference_long = None
        reference_lat = None

st.sidebar.subheader('Choose bodies/spacecraft and measured solar wind speeds')
with st.sidebar.beta_container():
    full_body_list = \
        st.sidebar.text_area('Bodies/spacecraft (scroll down for example list)',
                            'STEREO A, Earth, BepiColombo, PSP, Solar Orbiter, Mars',
                            height=50)
    vsw_list = \
        st.sidebar.text_area('Solar wind speed per body/SC (mind the order!)', '400, 400, 400, 400, 400, 400',
                            height=50)
    body_list = full_body_list.split(',')
    vsw_list = vsw_list.split(',')
    body_list = [body_list[i].strip() for i in range(len(body_list))]
    vsw_list = [int(vsw_list[i].strip()) for i in range(len(vsw_list))]

    all_bodies = print_body_list()
    # ugly workaround to not show the index in the table: replace them with empty strings
    all_bodies.reset_index(inplace=True)
    all_bodies.index = [""] * len(all_bodies)
    st.sidebar.table(all_bodies['Key'])

    st.sidebar.markdown('[Complete list of available bodies](https://ssd.jpl.nasa.gov/horizons.cgi?s_target=1#top)')

# initialize the bodies
c = HeliosphericConstellation(date, body_list, vsw_list, reference_long,
                              reference_lat)

# make the longitudinal constellation plot
plot_file = 'Solar-MACH_'+datetime.datetime.combine(d, t).strftime("%Y-%m-%d_%H-%M-%S")+'.png'

c.plot(
    plot_spirals=plot_spirals,                            # plot Parker spirals for each body
    plot_sun_body_line=plot_sun_body_line,                # plot straight line between Sun and body
    show_earth_centered_coord=show_earth_centered_coord,  # display Earth-aligned coordinate system
    reference_vsw=reference_vsw,                          # define solar wind speed at reference
    # outfile=plot_file                                     # output file (optional)
)

# download plot
filename = 'Solar-MACH_'+datetime.datetime.combine(d, t).strftime("%Y-%m-%d_%H-%M-%S")
plot2 = io.BytesIO()
plt.savefig(plot2, format='png', bbox_inches="tight")
# plot3 = base64.b64encode(plot2.getvalue()).decode("utf-8").replace("\n", "")
# st.markdown(f'<a href="data:file/png;base64,{plot3}" download="{plot_file}" target="_blank">Download figure as .png file</a>', unsafe_allow_html=True)

download_button_str = download_button(plot2.getvalue(), filename+'.png', f'Download figure as .png file', pickle_it=False)
st.markdown(download_button_str, unsafe_allow_html=True)

# display coordinates
st.dataframe(c.coord_table)

# download coordinates
# filename = 'Solar-MACH_'+datetime.datetime.combine(d, t).strftime("%Y-%m-%d_%H-%M-%S")
# csv = c.coord_table.to_csv().encode()
# b64 = base64.b64encode(csv).decode()
# st.markdown(f'<a href="data:file/csv;base64,{b64}" download="{filename}.csv" target="_blank">Download table as .csv file</a>', unsafe_allow_html=True)
download_button_str = download_button(c.coord_table, filename+'.csv', f'Download table as .csv file', pickle_it=False)
st.markdown(download_button_str, unsafe_allow_html=True)
# footer
st.markdown("""---""")
st.markdown('The *Solar MAgnetic Connection Haus* (Solar-MACH) tool is a \
            multi-spacecraft longitudinal configuration plotter. It was \
            originally developed at the University of Kiel, Germany, and further \
            discussed within the [ESA Heliophysics Archives USer (HAUS)]\
            (https://www.cosmos.esa.int/web/esdc/archives-user-groups/heliophysics) \
            group. It is now opened to everyone ([original code]\
            (https://github.com/esdc-esac-esa-int/Solar-MACH)).')

st.markdown('[Forked and modified](https://github.com/jgieseler/Solar-MACH) by \
            [J. Gieseler](https://jgieseler.github.io) \
            (University of Turku, Finland). [Get in contact](mailto:jan.gieseler@utu.fi?subject=Solar-MACH).')

st.markdown("""---""")
st.markdown('Powered by: \
            [<img src="https://matplotlib.org/stable/_static/logo2_compressed.svg" height="25">](https://matplotlib.org) \
            [<img src="https://streamlit.io/images/brand/streamlit-logo-secondary-colormark-darktext.svg" height="30">](https://streamlit.io) \
            [<img src="https://raw.githubusercontent.com/sunpy/sunpy-logo/master/generated/sunpy_logo_landscape.svg" height="30">](https://sunpy.org)', \
            unsafe_allow_html=True)
