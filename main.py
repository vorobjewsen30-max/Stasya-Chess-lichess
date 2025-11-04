import berserk
import chess
import chess.engine
import time
import logging
import random

class AdvancedLichessBot:
    def __init__(self, token):
        self.token = token
        self.session = berserk.TokenSession(token)
        self.client = berserk.Client(self.session)
        self.engine = chess.engine.SimpleEngine.popen_uci("stockfish.exe")
        
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        self.profile = self.client.account.get()
        self.logger.info(f"🎯 Бот {self.profile['username']} запущен!")
        
        # Расширенные настройки поведения
        self.settings = {
            'draw_accept_chance': 0.3,      # 30% шанс принять ничью
            'takeback_accept_chance': 0.2,  # 20% шанс принять отмену хода
            'resign_chance': 0.1,           # 10% шанс сдаться в плохой позиции
            'min_moves_for_draw': 10,       # Минимум ходов перед принятием ничьи
            'move_delay': 1.0,              # Задержка перед ходом (секунды)
        }
        
        self.logger.info("⚙️ Настройки бота:")
        for key, value in self.settings.items():
            self.logger.info(f"   {key}: {value}")
    
    def is_our_turn(self, moves, our_color):
        """Определяем, наш ли ход"""
        if not moves:
            return our_color == 'white'
        
        moves_list = moves.split()
        is_white_turn = len(moves_list) % 2 == 0
        return (our_color == 'white') == is_white_turn
    
    def should_accept_draw(self, game_id, move_count):
        """Определяем, стоит ли принимать ничью"""
        if move_count < self.settings['min_moves_for_draw']:
            self.logger.info(f"❌ Слишком рано для ничьи (ход {move_count})")
            return False
        
        if random.random() < self.settings['draw_accept_chance']:
            try:
                self.client.board.accept_draw(game_id)
                self.logger.info("🤝 Принял ничью!")
                return True
            except Exception as e:
                self.logger.error(f"❌ Ошибка: {e}")
        else:
            self.logger.info("🎲 Отклонил ничью")
        return False
    
    def should_accept_takeback(self, game_id):
        """Определяем, стоит ли принимать отмену хода"""
        if random.random() < self.settings['takeback_accept_chance']:
            try:
                self.client.board.accept_takeback(game_id)
                self.logger.info("↩️ Принял отмену хода!")
                return True
            except Exception as e:
                self.logger.error(f"❌ Ошибка: {e}")
        else:
            self.logger.info("🎲 Отклонил отмену хода")
        return False
    
    def consider_resignation(self, game_id, board):
        """Подумать о сдаче в плохой позиции"""
        if random.random() < self.settings['resign_chance']:
            try:
                # Простая оценка - если мало фигур, возможно сдаться
                if len(board.piece_map()) < 10:  # Мало фигур на доске
                    self.client.board.resign(game_id)
                    self.logger.info("🏳️ Сдался!")
                    return True
            except Exception as e:
                self.logger.error(f"❌ Ошибка сдачи: {e}")
        return False
    
    def play_game(self, game_id):
        """Играем партию с расширенной логикой"""
        self.logger.info(f"🎮 Игра {game_id}")
        our_id = self.profile['id']
        our_color = None
        move_count = 0
        
        try:
            for game_event in self.client.board.stream_game_state(game_id):
                if game_event['type'] == 'gameFull':
                    our_color = 'white' if game_event['white']['id'] == our_id else 'black'
                    self.logger.info(f"🎨 Я играю {our_color}")
                    
                    if our_color == 'white':
                        board = chess.Board()
                        result = self.engine.play(board, chess.engine.Limit(time=2.0))
                        self.client.board.make_move(game_id, result.move.uci())
                        self.logger.info(f"♟️ Первый ход: {result.move.uci()}")
                        move_count = 1
                
                elif game_event['type'] == 'gameState':
                    state = game_event
                    
                    if state.get('status') != 'started':
                        self.logger.info(f"🏁 Игра завершена: {state.get('status')}")
                        return
                    
                    moves = state.get('moves', '')
                    if moves and our_color and self.is_our_turn(moves, our_color):
                        self.logger.info("🤔 Мой ход! Анализирую...")
                        time.sleep(self.settings['move_delay'])
                        
                        # Строим доску
                        board = chess.Board()
                        moves_list = moves.split()
                        move_count = len(moves_list)
                        for move in moves_list:
                            board.push_uci(move)
                        
                        # Подумать о сдаче
                        if self.consider_resignation(game_id, board):
                            return
                        
                        # Сделать ход
                        result = self.engine.play(board, chess.engine.Limit(time=2.0))
                        self.client.board.make_move(game_id, result.move.uci())
                        self.logger.info(f"♟️ Ход {move_count + 1}: {result.move.uci()}")
                    
                    elif moves:
                        move_count = len(moves.split())
                        self.logger.debug(f"⏳ Жду хода... (ход {move_count})")
                
                elif game_event['type'] == 'chatLine':
                    chat = game_event
                    username = chat.get('username', '')
                    text = chat.get('text', '').lower()
                    
                    self.logger.info(f"💬 {username}: {text}")
                    
                    # Реагируем на разные предложения
                    if any(word in text for word in ['draw', 'ничья', 'peace', 'draw?']):
                        self.logger.info("🎲 Предложение ничьи")
                        self.should_accept_draw(game_id, move_count)
                    
                    elif any(word in text for word in ['takeback', 'отмена', 'back', 'undo']):
                        self.logger.info("🔄 Предложение отмены")
                        self.should_accept_takeback(game_id)
                
                elif game_event['type'] == 'takebackOffered':
                    self.logger.info("🔄 Предложение отмены хода")
                    self.should_accept_takeback(game_id)
        
        except Exception as e:
            self.logger.error(f"❌ Ошибка в игре: {e}")
    
    def run(self):
        """Основной цикл"""
        self.logger.info("👂 Ожидаю вызовы...")
        
        for event in self.client.board.stream_incoming_events():
            self.logger.info(f"📨 {event['type']}")
            
            if event['type'] == 'challenge':
                try:
                    self.client.challenges.accept(event['challenge']['id'])
                    self.logger.info("✅ Вызов принят")
                except Exception as e:
                    self.logger.error(f"❌ Ошибка: {e}")
            
            elif event['type'] == 'gameStart':
                self.play_game(event['game']['id'])

# ЗАПУСК ПРОДВИНУТОГО БОТА
if __name__ == "__main__":
    AdvancedLichessBot("lip_CmHWTJbgAP1K7YVcaAL6").run()
