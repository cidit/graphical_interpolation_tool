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

window = Tk()
# setting the title and
window.title("Plotting in Tkinter")
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


filename_label = Label(window, width=100, height=4)
filename_label.pack()
results_label = Label(window, width=80, height=4)
results_label.pack()

update_filename_label_effect = Effect(
    lambda: filename_label.configure(text=f"file opened: {filename()}")
)

# filename_log_on_update_effect = Effect(lambda: print(f"filename changed: {filename()}"))


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

click_data = Signal(None)


def reset_click_data_on_data_change_fn():
    data()  # simply bind this
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
    return f(selected_loss())
    # return np.interp(x=selected_loss(),
    #                  xp=data()["y"].iloc[::-1], # .iloc[::-1] reverses the frame. np.interp expects increasing data
    #                  fp=data()["x"].iloc[::-1],)


resulting_voltage = Computed(compute_resulting_voltage)

update_results_label_effect = Effect(
    lambda: results_label.configure(
        text=f"Selected loss:\t{selected_loss():.2}uW\nResulting voltage:\t{resulting_voltage():.2}V"
    )
)

log_click_data_effect = Effect(lambda: print(f"{selected_loss()}uW"))
log_resulting_voltage_effect = Effect(lambda: print(f"{resulting_voltage()}V"))
# update_selected

fig = Figure(figsize=(5, 5), dpi=100)
plot1 = fig.add_subplot(111)
canvas = FigureCanvasTkAgg(fig, master=window)
canvas.mpl_connect("button_press_event", click_data.set)


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
# run the gui
window.mainloop()
