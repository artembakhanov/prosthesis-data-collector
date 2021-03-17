import streamlit as st
import serial
from serial.tools import list_ports
from time import sleep
import SessionState

st.write("""# Hello""")

port_name = st.selectbox("Select PORT", [port.device for port in list_ports.comports()])
speed = st.selectbox("Select speed", [115200])
connect_button = st.empty()
disconnect_button = st.empty()
start_button = st.empty()

dataframe = []

state = SessionState.get(port=None, started=False, data=[])

if connect_button.button("Connect", key='connect'):
    state.port = serial.Serial(port=port_name, baudrate=115200,
                               bytesize=8, timeout=2, stopbits=serial.STOPBITS_ONE)
    connect_button.empty()

if disconnect_button.button("Disconnect", key="disconnect"):
    state.port.close()
    state.port = None
    disconnect_button.empty()

if state.port:
    connect_button.empty()
else:
    disconnect_button.empty()


chart = st.line_chart([[]], width=1200)

if start_button.button('Start', key='start'):
    start_button.empty()
    if st.button('Stop', key='stop'):
        state.data = []
        pass
    else:
        while 1:
            if state.port.in_waiting > 0:
                serialString = state.port.readline()
                new_data = list(map(int, serialString.decode('Ascii').split()))
                state.data.append(new_data)
                # chart.line_chart(state.data[-20:])
                chart.add_rows(new_data)
