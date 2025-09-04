import sys
from PyQt5 import QtWidgets
from PyQt5.uic import loadUi 

class GUI(QtWidgets.QMainWindow):
    def __init__(self):
        super(GUI, self).__init__()
        loadUi("Front-End/interface.ui", self)
        self.show()

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = GUI()
    sys.exit(app.exec_())