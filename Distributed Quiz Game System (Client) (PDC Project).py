import socket
import threading
import tkinter as tk
from tkinter import simpledialog, messagebox, scrolledtext
import json

class QuizClient:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Quiz Game")

        # Ask for server IP and port before connecting
        self.host = simpledialog.askstring("Server IP", "Enter server IP address:", parent=self.root)
        if not self.host:
            messagebox.showerror("Error", "Server IP is required")
            self.root.destroy()
            return

        port_str = simpledialog.askstring("Port", "Enter server port:", parent=self.root)
        if not port_str or not port_str.isdigit():
            messagebox.showerror("Error", "Valid server port is required")
            self.root.destroy()
            return
        self.port = int(port_str)

        try:
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.connect((self.host, self.port))
        except ConnectionRefusedError:
            messagebox.showerror("Error", f"Could not connect to server {self.host}:{self.port}")
            self.root.destroy()
            return

        self.name = simpledialog.askstring("Name", "Enter your name:", parent=self.root)
        if not self.name:
            self.name = "Anonymous"

        try:
            self.client.sendall((self.name + "\n").encode('utf-8'))
        except:
            messagebox.showerror("Error", "Connection failed")
            self.root.destroy()
            return

        self.create_gui()
        threading.Thread(target=self.receive, daemon=True).start()
        self.root.mainloop()

    def create_gui(self):
        self.root.geometry("500x600")
        self.root.configure(bg='#f0f0f0')

        self.timer_frame = tk.Frame(self.root, bg='yellow')
        self.timer_frame.pack(fill='x', padx=5, pady=5)
        self.timer_label = tk.Label(self.timer_frame, text="Time left: --", font=('Arial', 12), bg='yellow')
        self.timer_label.pack()

        self.q_frame = tk.Frame(self.root, bg='white', padx=10, pady=10)
        self.q_frame.pack(pady=10, fill='x')

        self.question_num_label = tk.Label(self.q_frame, text="", font=('Arial', 10), bg='white')
        self.question_num_label.pack(anchor='w')

        self.q_label = tk.Label(self.q_frame, text="Waiting for players...", font=('Arial', 14), 
                              bg='white', wraplength=450, justify='left')
        self.q_label.pack()

        self.result_label = tk.Label(self.root, text="", font=('Arial', 12))
        self.result_label.pack(pady=5)

        self.btn_frame = tk.Frame(self.root)
        self.btn_frame.pack(pady=10)

        self.buttons = []
        for i in range(4):
            btn = tk.Button(self.btn_frame, text="", width=30, bg='#e0e0e0', 
                          activebackground='#d0d0d0', font=('Arial', 10),
                          command=lambda i=i: self.send_answer(i))
            btn.pack(pady=5)
            self.buttons.append(btn)

        self.chat_frame = tk.Frame(self.root, bg='#f8f8f8')
        self.chat_frame.pack(pady=10, fill='both', expand=True, padx=10)

        self.chat_box = scrolledtext.ScrolledText(self.chat_frame, state='disabled', 
                                                height=10, wrap=tk.WORD, font=('Arial', 10))
        self.chat_box.pack(fill='both', expand=True)

        self.chat_entry = tk.Entry(self.chat_frame, font=('Arial', 10))
        self.chat_entry.pack(fill='x', pady=(5,0))
        self.chat_entry.bind('<Return>', self.send_chat)

        self.score_label = tk.Label(self.root, text="Scoreboard:", bg='lightblue',
                                  font=('Arial', 10), padx=10, pady=5, justify='left', anchor='w')
        self.score_label.pack(pady=5, fill='x')

        self.timer_running = False
        self.time_left = 0
        self.timer_update_id = None

    def update_timer(self):
        if self.timer_running and self.time_left > 0:
            self.time_left -= 1
            self.timer_label.config(text=f"Time left: {self.time_left}s")
            self.timer_update_id = self.root.after(1000, self.update_timer)
        else:
            self.timer_running = False
            for btn in self.buttons:
                btn.config(state='disabled')

    def start_timer(self, time_limit):
        if self.timer_update_id:
            self.root.after_cancel(self.timer_update_id)
        self.time_left = time_limit
        self.timer_running = True
        self.timer_label.config(text=f"Time left: {self.time_left}s")
        self.update_timer()

    def send_answer(self, index):
        try:
            message = json.dumps({
                "type": "answer", 
                "name": self.name, 
                "answer": index
            }) + "\n"
            self.client.sendall(message.encode('utf-8'))
            for btn in self.buttons:
                btn.config(state='disabled')
            if self.timer_update_id:
                self.root.after_cancel(self.timer_update_id)
                self.timer_running = False
        except Exception as e:
            print(f"Error sending answer: {e}")

    def send_chat(self, event):
        msg = self.chat_entry.get()
        if msg:
            try:
                message = json.dumps({
                    "type": "chat", 
                    "name": self.name, 
                    "msg": msg
                }) + "\n"
                self.client.sendall(message.encode('utf-8'))
                self.chat_entry.delete(0, tk.END)
            except Exception as e:
                print(f"Error sending chat: {e}")

    def receive(self):
        buffer = ""
        while True:
            try:
                data = self.client.recv(2048).decode('utf-8')
                if not data:
                    break

                buffer += data
                while "\n" in buffer:
                    message, buffer = buffer.split("\n", 1)
                    if message:
                        try:
                            data = json.loads(message)

                            if data['type'] == 'question':
                                self.root.after(0, self.show_question, data)
                            elif data['type'] == 'result':
                                self.root.after(0, self.show_result, data)
                            elif data['type'] == 'score':
                                self.root.after(0, self.update_score, data)
                            elif data['type'] == 'end':
                                self.root.after(0, self.end_game, data)
                            elif data['type'] == 'chat':
                                self.root.after(0, self.display_chat, data)

                        except json.JSONDecodeError:
                            print("Invalid JSON received:", message)

            except Exception as e:
                print(f"Error in receive: {e}")
                break

    def show_question(self, data):
        self.question_num_label.config(
            text=f"Question {data['question_num']} of {data['total_questions']}")
        self.q_label.config(text=data['question'])
        for i in range(4):
            self.buttons[i].config(text=data['options'][i], bg='#e0e0e0', state='normal')
        self.result_label.config(text="")
        self.start_timer(data['time_limit'])

    def show_result(self, data):
        if data.get('timeout'):
            message = "Time's up! -1 point to all players"
        elif data['player'] == self.name:
            if data['correct']:
                message = "You answered correctly! (+1 point)"
            else:
                message = "Your answer was wrong! (-1 point)"
        else:
            if data['correct']:
                message = f"{data['player']} answered correctly!"
            else:
                message = f"{data['player']} answered wrong!"

        self.result_label.config(text=message)

        for btn in self.buttons:
            btn.config(state='disabled')
        if self.timer_update_id:
            self.root.after_cancel(self.timer_update_id)
            self.timer_running = False

        if data.get('move_next'):
            self.root.after(1000, lambda: self.result_label.config(text=""))

    def update_score(self, data):
        sorted_scores = sorted(data['scores'].items(), key=lambda x: x[1], reverse=True)
        score_text = "\n".join([f"{name}: {score}" for name, score in sorted_scores])
        self.score_label.config(text="Scoreboard:\n" + score_text)

    def end_game(self, data):
        messagebox.showinfo("Game Over", f"Winner: {data['winner']}")
        self.root.quit()

    def display_chat(self, data):
        self.chat_box['state'] = 'normal'
        self.chat_box.insert(tk.END, f"{data['name']}: {data['msg']}\n")
        self.chat_box['state'] = 'disabled'
        self.chat_box.see(tk.END)

if __name__ == '__main__':
    QuizClient()

