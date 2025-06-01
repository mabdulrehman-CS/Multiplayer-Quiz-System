import socket
import threading
import json
import time
import random

questions = [
    {"question": "What is the capital of France?", "options": ["Paris", "London", "Berlin", "Madrid"], "answer": 0},
    {"question": "What is 5 + 7?", "options": ["10", "11", "12", "13"], "answer": 2},
    {"question": "Who wrote 'Hamlet'?", "options": ["Shakespeare", "Dickens", "Tolkien", "Rowling"], "answer": 0},
    {"question": "What is the largest planet in our solar system?", "options": ["Earth", "Mars", "Jupiter", "Saturn"], "answer": 2},
    {"question": "Which country is home to the kangaroo?", "options": ["South Africa", "Brazil", "Australia", "New Zealand"], "answer": 2},
    {"question": "What is the chemical symbol for gold?", "options": ["Go", "Gd", "Au", "Ag"], "answer": 2},
    {"question": "In which year did World War II end?", "options": ["1943", "1945", "1947", "1950"], "answer": 1},
    {"question": "Which of these is not a primary color?", "options": ["Red", "Blue", "Green", "Yellow"], "answer": 3},
    {"question": "What is the capital of Japan?", "options": ["Beijing", "Seoul", "Tokyo", "Bangkok"], "answer": 2},
    {"question": "Which planet is known as the Red Planet?", "options": ["Venus", "Mars", "Jupiter", "Saturn"], "answer": 1},
]

random.shuffle(questions)

class QuizServer:
    def __init__(self, host='localhost', port=12345):
        self.clients = []
        self.client_names = {}
        self.scores = {}
        self.current_question = 0
        self.lock = threading.Lock()
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((host, port))
        self.server.listen(5)
        print(f"Server started on {host}:{port}")
        self.required_players = 2
        self.game_started = False
        self.waiting_for_answers = False
        self.question_timer = None
        self.timeout = 20

    def broadcast(self, data):
        message = (json.dumps(data) + "\n").encode('utf-8')
        disconnected = []
        for client in self.clients:
            try:
                client.sendall(message)
            except:
                disconnected.append(client)
        for dc in disconnected:
            self.remove_client(dc)

    def remove_client(self, conn):
        with self.lock:
            if conn in self.clients:
                name = self.client_names.get(conn, "Unknown")
                self.clients.remove(conn)
                if name in self.scores:
                    del self.scores[name]
                if conn in self.client_names:
                    del self.client_names[conn]
                print(f"{name} disconnected")
                self.broadcast({"type": "chat", "name": "Server", "msg": f"{name} left the game"})
                # Stop game if not enough players
                if self.game_started and len(self.clients) < self.required_players:
                    self.broadcast({"type": "end", "winner": "No winner - not enough players"})
                    self.game_started = False
                    if self.question_timer:
                        self.question_timer.cancel()

    def handle_client(self, conn):
        try:
            name_data = b""
            while True:
                chunk = conn.recv(1024)
                if not chunk:
                    break
                name_data += chunk
                if b"\n" in chunk:
                    break

            if not name_data:
                return

            name = name_data.decode('utf-8').strip()

            with self.lock:
                self.clients.append(conn)
                self.client_names[conn] = name
                self.scores[name] = 0
                print(f"{name} joined the game.")
                self.broadcast({"type": "chat", "name": "Server", "msg": f"{name} joined the game"})

            if len(self.clients) == self.required_players and not self.game_started:
                self.game_started = True
                threading.Thread(target=self.start_game).start()

            buffer = ""
            while True:
                try:
                    data = conn.recv(2048).decode('utf-8')
                    if not data:
                        break
                    buffer += data
                    while "\n" in buffer:
                        message, buffer = buffer.split("\n", 1)
                        if message:
                            data = json.loads(message)
                            if data['type'] == 'answer':
                                self.handle_answer(data, conn)
                            elif data['type'] == 'chat':
                                self.broadcast(data)
                except json.JSONDecodeError:
                    print(f"Invalid JSON from {name}: {buffer}")
                    buffer = ""
                except Exception as e:
                    print(f"Error handling client {name}: {e}")
                    break

        except Exception as e:
            print(f"Client handler error: {e}")
        finally:
            self.remove_client(conn)

    def handle_answer(self, data, conn):
        with self.lock:
            if not self.waiting_for_answers:
                return

            name = data['name']
            print(f"Received answer from {name}")

            correct_answer = questions[self.current_question]['answer']
            is_correct = data['answer'] == correct_answer

            if is_correct:
                self.scores[name] += 1
            else:
                self.scores[name] -= 1

            print(f"Scores after answer from {name}: {self.scores}")

            self.broadcast({
                "type": "result",
                "player": name,
                "correct": is_correct,
                "move_next": True
            })
            self.broadcast({"type": "score", "scores": self.scores})

            self.waiting_for_answers = False
            if self.question_timer:
                self.question_timer.cancel()
            self.move_to_next_question()

    def move_to_next_question(self):
        time.sleep(1)
        self.current_question += 1
        self.send_question()

    def send_question(self):
        if self.current_question >= len(questions):
            winner = max(self.scores, key=self.scores.get) if self.scores else "No players"
            self.broadcast({"type": "end", "winner": winner})
            self.game_started = False
            return

        q = questions[self.current_question]
        self.broadcast({
            "type": "question",
            "question": q['question'],
            "options": q['options'],
            "question_num": self.current_question + 1,
            "total_questions": len(questions),
            "time_limit": self.timeout
        })
        self.waiting_for_answers = True

        self.question_timer = threading.Timer(self.timeout, self.timeout_handler)
        self.question_timer.start()

    def timeout_handler(self):
        with self.lock:
            if self.waiting_for_answers:
                print("Time's up! Deducting points from all players")
                for name in self.scores:
                    self.scores[name] -= 1
                print(f"Scores after timeout: {self.scores}")

                self.broadcast({
                    "type": "result",
                    "player": "Server",
                    "timeout": True,
                    "move_next": True
                })
                self.broadcast({"type": "score", "scores": self.scores})

                self.waiting_for_answers = False
                if self.question_timer:
                    self.question_timer.cancel()
                self.move_to_next_question()

    def start_game(self):
        self.broadcast({"type": "chat", "name": "Server", "msg": "Game starting!"})
        time.sleep(1)
        self.send_question()

    def run(self):
        try:
            while True:
                conn, addr = self.server.accept()
                print(f"New connection from {addr}")
                threading.Thread(target=self.handle_client, args=(conn,), daemon=True).start()
        except KeyboardInterrupt:
            print("Shutting down server...")
        finally:
            self.server.close()

if __name__ == '__main__':
    QuizServer().run()
