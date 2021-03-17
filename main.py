import sys
from threading import Thread

import serial
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QMainWindow, QVBoxLayout, QComboBox, QHBoxLayout, \
    QPushButton, QAction, QRadioButton
from PyQt5 import QtCore
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from serial.tools import list_ports
import numpy as np
import os
from config import CLASSES
from random import choice
import uuid

app = QApplication(sys.argv)

INIT = 0
CONNECTED = 1
STARTED = 2

pixmaps = {k: QPixmap(v).scaled(128, 128, QtCore.Qt.KeepAspectRatio) for k, v in CLASSES.items()}


class DataThread:
    def __init__(self):
        self._running = True

    def terminate(self):
        self._running = False

    def run(self, controller, port):
        while self._running:
            if port.in_waiting > 0:
                serialString = port.readline()
                new_data = np.array(list(map(int, serialString.decode('Ascii').split())))
                controller.processNewData(new_data)


class MplCanvas(FigureCanvas):

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111, xlim=(-2, 0), ylim=(-500, 2048 * 2))
        super(MplCanvas, self).__init__(fig)


class AppUI(QMainWindow):

    def __init__(self):
        """View initializer."""
        super().__init__()
        # Set some main window's properties
        self.setWindowTitle('Prothesis Data Collector')
        # Set the central widget and the general layout
        self.generalLayout = QVBoxLayout()
        self._centralWidget = QWidget(self)
        self.setCentralWidget(self._centralWidget)
        self._centralWidget.setLayout(self.generalLayout)
        # Create the display and the buttons
        self.titleText = QLabel("<h1>Data Collector</h1>")
        self.generalLayout.addWidget(self.titleText)

        self._comPortsWidget = QWidget(self)
        self._comPortsLayout = QHBoxLayout()
        self._comPortsWidget.setLayout(self._comPortsLayout)
        self.generalLayout.addWidget(self._comPortsWidget)

        self.comPortsBox = QComboBox()
        self._comPortsLayout.addWidget(self.comPortsBox, stretch=4)

        self.connectButton = QPushButton("Connect")
        self._comPortsLayout.addWidget(self.connectButton, stretch=1)

        self.startButton = QPushButton("Start")
        self.startButton.setVisible(False)

        self.stopButton = QPushButton("Stop")
        self.stopButton.setVisible(False)

        self._comPortsLayout.addWidget(self.startButton)
        self._comPortsLayout.addWidget(self.stopButton)

        self.testButton = QRadioButton("Test?")
        self.testButton.setChecked(False)
        self.generalLayout.addWidget(self.testButton)

        self.canvas = MplCanvas(self, width=5, height=4, dpi=100)
        self.lines = []
        self.generalLayout.addWidget(self.canvas)

        self.instructionText = QLabel("Nothing")
        self.instructionText.setVisible(False)
        self.generalLayout.addWidget(self.instructionText)

        self.instructionImage = QLabel()
        self.instructionImage.setVisible(False)
        self.generalLayout.addWidget(self.instructionImage)

    def updatePlots(self, ydata):
        for i, line in enumerate(self.lines):
            line.set_ydata(ydata[:, i])

        self.canvas.draw()


class AppController:
    def __init__(self, view_, model):
        self._view = view_
        self._second_view = None
        self._model = model

        self.dataThread = None

        self._initView()
        self._connectSignals()

    def _connectSignals(self):
        self._view.connectButton.clicked.connect(self._connectClick)
        self._view.startButton.clicked.connect(self._startClick)
        self._view.stopButton.clicked.connect(self._stopClick)

        self.timer = QtCore.QTimer()
        self.timer.setInterval(50)
        self.timer.timeout.connect(self._updatePorts)
        self.timer.start()

        self._collectTimer = QtCore.QTimer()
        self._collectTimer.setSingleShot(True)
        self._collectTimer.timeout.connect(self._collectData)

        self._changeGestureTimer = QtCore.QTimer()
        self._changeGestureTimer.setInterval(3500)
        self._changeGestureTimer.timeout.connect(self._changeGesture)

    def _startClick(self):
        self._setState(STARTED)
        self._model.test = self._view.testButton.isChecked()
        self._changeGestureTimer.start()

    def _stopClick(self):
        self._setState(CONNECTED)
        self._changeGestureTimer.stop()

    def stopDataCollection(self):
        self._second_view.close()
        self._second_view = None

    def _connectClick(self):
        self._model.connected = not self._model.connected
        if self._model.connected:
            self._connect()
        else:
            self._disconnect()

    def _updatePorts(self):
        newPorts = self._model.updatePorts()
        if newPorts is not None:
            self._view.comPortsBox.clear()
            self._view.comPortsBox.addItems(newPorts)

    def _initView(self):
        self._view.comPortsBox.addItems(self._model.ports)
        self._view.lines = self._view.canvas.axes.plot(self._model.xdata, self._model.ydata)
        for i, line in enumerate(self._view.lines):
            line.set_label(f"{i}".zfill(2))
        self._view.canvas.axes.legend(bbox_to_anchor=(1, 1), loc='upper left', fontsize='xx-small')

    def _connect(self):
        self._model.connect(str(self._view.comPortsBox.currentText()))
        self._changeGestureTimer.stop()
        self._setState(CONNECTED)

        self.dataThread = DataThread()
        t = Thread(target=self.dataThread.run, args=(self, self._model.connectedPort))
        t.start()

    def _disconnect(self):
        self._model.disconnect()
        self.dataThread.terminate()

        self._changeGestureTimer.stop()
        self._setState(INIT)

    def processNewData(self, newData):
        ydata = self._model.processNewData(newData)
        if ydata is not None:
            self._view.updatePlots(ydata)

    def _changeGesture(self):
        if self._model.currentGesture is not None and not self._model.test:
            # collect here
            name = uuid.uuid1().hex
            np.savetxt(os.path.join(self._model.dirs[self._model.currentGesture], f"{name}.csv"),
                       self._model.currentData, delimiter=",")

        self._model.currentGesture = choice(list(set(CLASSES) - {self._model.currentGesture}))
        self._view.instructionText.setText(self._model.currentGesture)
        self._view.instructionImage.setPixmap(pixmaps[self._model.currentGesture])
        self._view.instructionImage.show()
        self._collectTimer.start(600)

        # self._co

    def _collectData(self):
        self._model.currentData = np.empty((0, 10))

    def _setState(self, state):
        if state == INIT:
            self._view.startButton.setVisible(False)
            self._view.stopButton.setVisible(False)
            self._view.connectButton.setText("Connect")
            self._view.instructionText.setVisible(False)
            self._view.instructionImage.setVisible(False)
            self._model.currentGesture = None

        elif state == CONNECTED:
            self._view.connectButton.setText("Disconnect")
            self._view.startButton.setVisible(True)
            self._view.stopButton.setVisible(False)
            self._view.instructionText.setVisible(False)
            self._view.instructionImage.setVisible(False)

            self._model.currentGesture = None


        elif state == STARTED:
            self._view.startButton.setVisible(False)
            self._view.stopButton.setVisible(True)
            self._view.instructionText.setVisible(True)
            self._view.instructionImage.setVisible(True)
            self._view.instructionText.setText("Please be ready to start...")


class AppModel:

    def __init__(self, col_dir="collected"):

        self.xdata = np.linspace(-2, 0, 256)
        self.ydata = np.zeros((256, 10))
        self.update = 0
        self.update_rate = 4

        self.connected = False
        self.connectedPort = None
        self.ports = []

        self._dir = col_dir
        root, dirs, files = next(os.walk(self._dir))

        self._user_number = int(max(dirs + ["-1"])) + 1

        self._user_dir = os.path.join(root, str(self._user_number).zfill(4))
        os.mkdir(self._user_dir)

        self.dirs = {}
        for clazz in CLASSES:
            self.dirs[clazz] = os.path.join(self._user_dir, clazz)
            os.mkdir(self.dirs[clazz])

        self.currentGesture = None
        self.currentData = np.empty((0, 10))
        self.test = False

    def updatePorts(self):
        new_ports = [port.device for port in list_ports.comports()]
        if set(new_ports) != set(self.ports):
            if self.connectedPort is not None and self.connectedPort.port not in new_ports:
                self.disconnect()

            self.ports = new_ports
            return self.ports

    def connect(self, portName):
        if self.connectedPort is not None:
            self.connectedPort.close()
            self.connectedPort = None

        # try here?
        self.connectedPort = serial.Serial(port=portName, baudrate=115200,
                                           bytesize=8, timeout=2, stopbits=serial.STOPBITS_ONE)

    def disconnect(self):
        if self.connectedPort is not None:
            self.connectedPort.close()
            self.connectedPort = None

    def processNewData(self, newData):
        if newData.reshape((1, -1)).shape == (1, 10):
            # otherwise the data is corrupted
            self.update = (self.update + 1) % self.update_rate
            self.ydata = np.append(self.ydata[1:], newData.reshape((1, -1)), axis=0)

            self.currentData = np.append(self.currentData, newData.reshape((1, -1)), axis=0)

            if self.update == 0:
                return self.ydata
            else:
                return None


pycalc = QApplication(sys.argv)
# Show the calculator's GUI
view = AppUI()
view.show()
model = AppModel()
controller = AppController(view_=view, model=model)
# Create instances of the model and the controller
sys.exit(pycalc.exec_())
