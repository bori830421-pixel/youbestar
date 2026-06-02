class Memory:
    def __init__(self):
        self.history = []

    def add(self, user_input: str, action: str, result: str) -> None:
        self.history.append(
            {
                "user": user_input,
                "action": action,
                "result": result,
            }
        )

    def get_summary(self) -> str:
        recent_history = self.history[-20:]
        return "\n".join(
            f"{item['user']} -> {item['action']} -> {item['result']}" for item in recent_history
        )
