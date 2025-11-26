"""what to do:

take calib file (vlotage for loss)
desired loss dbdb selection
-> outputs corresponding voltage to match the selected loss
button that outputs the voltage to the NI myDAQ

"""

import tkinter as tk
from reaktiv import Signal, Computed, Effect, LinkedSignal
import csv
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.backend_bases import MouseButton
from pandas import DataFrame
import sys
from scipy import interpolate
import nidaqmx
import math
import numpy as np

window = tk.Tk()
window.title("Graphical interpolation tool")

main_frame = tk.Frame(window, padx=10, pady=10)
main_frame.grid(column=0, row=0, sticky=(tk.N, tk.W,tk.E,tk.S))


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
            data["y"].append(10*math.log10(csvstr_to_flt(row[1])/1e6))
        # data["y"] = [data["y"][0]].extend([d - data["y"][0] for d in data["y"][1:]]) # rectify data with initial
        m = np.max(data["y"])
        data["y"] = [y - m for y in data["y"]]
            
        return DataFrame.from_dict(data)


data = Computed(parse_data)

file_frame = tk.Frame(main_frame, pady=5, padx=3)
file_frame.grid(column=0, row=0, sticky=(tk.W,tk.E))

def browse_file_fn():
    file_name = tk.filedialog.askopenfilename(
        filetypes=[("CSV", "*.csv")],
        title="Select the data file",
    )
    filename.set(file_name)


browse_file_btn = tk.Button(
    master=file_frame,
    command=browse_file_fn,
    height=2,
    width=8,
    text="browse file",
)
browse_file_btn.grid(column=0, row=0, sticky=(tk.W, tk.E))


filename_label = tk.Label(file_frame, anchor=tk.W, justify="left", wraplength=400)
filename_label.grid(column=1, row=0, sticky=(tk.W, tk.E))

results_frame = tk.Frame(main_frame)
results_frame.grid(column=0, row=1, sticky=(tk.W,tk.E))

results_label = tk.Label(results_frame, height=4, anchor="w", justify="left")
results_label.grid(column=0, row=2, sticky=(tk.N, tk.W,tk.E,tk.S))

update_filename_label_effect = Effect(
    lambda: filename_label.configure(text=f"file opened: {filename()}")
)

filename_log_on_update_effect = Effect(lambda: print(f"filename changed: {filename()}"))

send_to_nidaq = Signal(False)
send_to_nidaq_btn = tk.Button(
    master=results_frame,
    command=lambda: send_to_nidaq.update(lambda old: not old),
    height=2,
    width=20,
)
send_to_nidaq_btn.grid(column=1, row=3, sticky=(tk.N, tk.W,tk.E,tk.S))


def update_send_to_nidaq_btn_fn():
    if send_to_nidaq():
        send_to_nidaq_btn.configure(text="Sending voltage to nidaq", bg="green")
    else:
        send_to_nidaq_btn.configure(text="Not interacting with nidaq", bg="red")


update_send_to_nidaq_btn_effect = Effect(update_send_to_nidaq_btn_fn)

click_data = Signal(None)

fig = Figure(figsize=(5, 5), dpi=100)
plot1 = fig.add_subplot(111)
canvas = FigureCanvasTkAgg(fig, master=results_frame)
canvas.mpl_connect("button_press_event", click_data.set)
canvas.mpl_connect("motion_notify_event", click_data.set)


def reset_click_data_on_data_change_fn():
    data()  # just used to bind the signal to the effect
    click_data.set(None)


reset_click_data_on_data_change_effect = Effect(reset_click_data_on_data_change_fn)


def compute_selected_loss(new_click_data, prev_selected_loss):
    if new_click_data is None:
        return None
    if new_click_data.button != MouseButton.LEFT:
        return prev_selected_loss.value if prev_selected_loss else None
    return new_click_data.ydata


selected_loss = LinkedSignal(source=click_data, computation=compute_selected_loss)

class EntryWithPlaceholder(tk.Entry):
    def __init__(self, *args, **kwargs):
        self.placeholder = kwargs.pop("placeholder", "")
        super().__init__(*args, **kwargs)

        self.insert("end", self.placeholder)
        self.bind("<FocusIn>", self.remove_placeholder)
        self.bind("<FocusOut>", self.add_placeholder)

    def remove_placeholder(self, _event):
        """Remove placeholder text, if present"""
        if self.get() == self.placeholder:
            self.delete(0, "end")

    def add_placeholder(self, _event):
        """Add placeholder text if the widget is empty"""
        if self.placeholder and self.get() == "":
            self.insert(0, self.placeholder)

loss_entry = tk.StringVar()
loss_entry_box = EntryWithPlaceholder(results_frame, textvariable=loss_entry, width=30, placeholder="or type the loss yourself (in db)")
loss_entry_box.bind('<Return>', lambda _e: selected_loss.set(float(loss_entry.get())))
loss_entry_box.grid(column=0, row=3)

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
        text=f"Selected loss:\t{sl:.3}dBm\nResulting voltage:\t{rv:.3}V"
    )


update_results_label_effect = Effect(update_results_label_fn)


def send_voltage_to_nidaq_fn():
    if not send_to_nidaq() or resulting_voltage() is None:
        return
    try:
        with nidaqmx.Task() as task:
            task.ao_channels.add_ao_voltage_chan("myDAQ2/ao1")
            task.write([resulting_voltage()])
    except nidaqmx.errors.DaqNotFoundError as _:
        print("No NIDAQ available! please ensure one is connected first")
        send_to_nidaq.set(False)

send_voltage_to_nidaq_effect = Effect(send_voltage_to_nidaq_fn)


def draw_plot():
    plot1.axes.clear()
    plot1.set_xlabel("Voltage (V)")
    plot1.set_ylabel("Loss (dBm)")

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
    canvas.get_tk_widget().grid(column=0, row=0, columnspan=2, rowspan=2, sticky=(tk.N, tk.W,tk.E,tk.S))
    # canvas.get_tk_widget().pack()


make_plot_effect = Effect(draw_plot)


window.bind("<Escape>", sys.exit)
window.mainloop()
