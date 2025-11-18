"""what to do:

take calib file (vlotage for loss)
desired loss dbdb selection
-> outputs corresponding voltage to match the selected loss
button that outputs the voltage to the NI myDAQ

"""

from tkinter import Tk, Button, filedialog, Label
from reaktiv import Signal, Computed, Effect
import csv
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.backend_bases import MouseButton
from pandas import DataFrame
import sys
from scipy import interpolate
import nidaqmx

window = Tk()
# setting the title and
window.title("Graphical interpolation tool")
# setting the dimensions of
# the main window
window.geometry("1000x750")


# plot function is created for
# plotting the graph in
# tkinter window
def plot(window: Tk):
    # the figure that will contain the plot
    fig = Figure(figsize=(5, 5), dpi=100)
    # list of squares
    y = [i**2 for i in range(101)]
    # adding the subplot
    plot1 = fig.add_subplot(111)
    # plotting the graph
    plot1.plot(y)
    # creating the Tkinter canvas
    # containing the Matplotlib figure
    canvas = FigureCanvasTkAgg(fig, master=window)
    canvas.draw()
    # placing the canvas on the Tkinter window
    canvas.get_tk_widget().pack()
    # creating the Matplotlib toolbar
    toolbar = NavigationToolbar2Tk(canvas, window)
    toolbar.update()
    # placing the toolbar on the Tkinter window
    canvas.get_tk_widget().pack()


# button that would displays the plot
# plot_button = Button(master=window, command=plot, height=2, width=10, text="Plot")
# plot_button.pack()

filename = Signal(None)


def parse_data():
    def csvstr_to_flt(str):
        return float(str.replace(",", "."))

    if not filename():
        return None
    with open(filename()) as f:
        data = {
            "x": [],
            "y": [],
        }
        reader = csv.reader(f)
        for row in reader:
            data["x"].append(csvstr_to_flt(row[0]))
            data["y"].append(csvstr_to_flt(row[1]))
        return DataFrame.from_dict(data)


data = Computed(parse_data)


def browse_file_fn():
    file_name = filedialog.askopenfilename(
        filetypes=[("CSV", "*.csv")],
        title="Select the data file",
    )
    filename.set(file_name)


browse_file_btn = Button(
    master=window,
    command=browse_file_fn,
    height=2,
    width=10,
    text="browse file",
)
browse_file_btn.pack()


filename_label = Label(window, width=100, height=1)
filename_label.pack()

results_label = Label(window, height=4, anchor="w", justify="left")
results_label.pack()

update_filename_label_effect = Effect(
    lambda: filename_label.configure(text=f"file opened: {filename()}")
)

filename_log_on_update_effect = Effect(lambda: print(f"filename changed: {filename()}"))

send_to_nidaq = Signal(False)
send_to_nidaq_btn = Button(
    master=window,
    command=lambda: send_to_nidaq.update(lambda old: not old),
    height=2,
    width=20,
)
send_to_nidaq_btn.pack()


def update_send_to_nidaq_btn_fn():
    if send_to_nidaq():
        send_to_nidaq_btn.configure(text="Sending voltage to nidaq", bg="green")
    else:
        send_to_nidaq_btn.configure(text="Not interacting with nidaq", bg="red")


update_send_to_nidaq_btn_effect = Effect(update_send_to_nidaq_btn_fn)

click_data = Signal(None)

fig = Figure(figsize=(5, 5), dpi=100)
plot1 = fig.add_subplot(111)
canvas = FigureCanvasTkAgg(fig, master=window)
canvas.mpl_connect("button_press_event", click_data.set)


def reset_click_data_on_data_change_fn():
    data()  # just used to bind the signal to the effect
    click_data.set(None)


reset_click_data_on_data_change_effect = Effect(reset_click_data_on_data_change_fn)


def compute_selected_loss():
    if click_data() is None:
        return None
    if click_data().button != MouseButton.LEFT:
        return None
    return click_data().ydata


selected_loss = Computed(compute_selected_loss)


def compute_resulting_voltage():
    if selected_loss() is None or data() is None:
        return None
    f = interpolate.interp1d(x=data()["y"], y=data()["x"], assume_sorted=False)
    if data()["y"].min() <= selected_loss() <= data()["y"].max():
        return f(selected_loss())
    else:
        return None


resulting_voltage = Computed(compute_resulting_voltage)


def update_results_label_fn():
    sl = selected_loss() if selected_loss() is not None else 0.0
    rv = resulting_voltage() if resulting_voltage() is not None else 0.0
    results_label.configure(
        text=f"Selected loss:\t{sl:.2}uW\nResulting voltage:\t{rv:.2}V"
    )


update_results_label_effect = Effect(update_results_label_fn)


def send_voltage_to_nidaq_fn():
    if not send_to_nidaq() or resulting_voltage() is None:
        return
    try:
        with nidaqmx.Task() as task:
            task.ao_channels.add_ao_voltage_chan("Dev1/ao0")
            task.write(resulting_voltage())
    except nidaqmx.errors.DaqNotFoundError as _:
        print("No NIDAQ available! please ensure one is connected first")
        send_to_nidaq.set(False)

send_voltage_to_nidaq_effect = Effect(send_voltage_to_nidaq_fn)


def draw_plot():
    plot1.axes.clear()
    plot1.set_xlabel("Voltage (V)")
    plot1.set_ylabel("Loss (uW)")

    if data() is not None:
        plot1.plot(data()["x"], data()["y"])
        if click_data() is not None:
            plot1.hlines(
                click_data().ydata,
                xmin=data()["x"].min(),
                xmax=data()["x"].max(),
                colors="r",
                linestyles="dotted",
            )

    canvas.draw()
    # canvas.get_tk_widget().bind("<Button-1>", lambda e: print(e.x, e.y))
    # placing the canvas on the Tkinter window
    canvas.get_tk_widget().pack()


make_plot_effect = Effect(draw_plot)


window.bind("<Escape>", sys.exit)
window.mainloop()
