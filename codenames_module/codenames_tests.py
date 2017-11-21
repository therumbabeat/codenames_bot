import unittest
import random

import faker

from .codenames import (
    Team, CardType, GameBoard, IrcCodenamesGame, TEAM_CARD_COUNT,
    BYSTANDER_CARD_COUNT, ASSASSIN_CARD_COUNT)

random.seed(0)
fake = faker.Faker()


class GameBoardTestCase(unittest.TestCase):

    def setUp(self):
        self.starting_team = Team.red
        self.spy_key = IrcCodenamesGame.generate_spy_key(self.starting_team)
        self.card_type_coordinates = self.find_card_type_example_coordinates(
            self.spy_key)
        self.word_deck = list(set(fake.words(nb=100)))

    @staticmethod
    def find_card_type_example_coordinates(spy_key):
        card_type_coordinates = dict()
        unfound_card_types = list(CardType)
        indices = GameBoard.get_grid_indices()
        while unfound_card_types:
            i, j = next(indices)
            card_type = spy_key[i][j]
            if card_type in unfound_card_types:
                unfound_card_types.remove(card_type)
                card_type_coordinates[card_type] = (i, j)
        return card_type_coordinates

    @staticmethod
    def find_all_card_type_coordinates(spy_key, card_type):
        coordinates = []
        indices = GameBoard.get_grid_indices()
        for i, j in indices:
            if spy_key[i][j] is card_type:
                coordinates.append((i, j))
        return coordinates

    def test_setup(self):
        board = GameBoard(self.word_deck, self.spy_key)
        self.assertEqual(board.cards_remaining(self.starting_team.card_type()),
                         TEAM_CARD_COUNT + 1)
        self.assertEqual(board.cards_remaining(self.starting_team.other()
                                               .card_type()), TEAM_CARD_COUNT)
        self.assertEqual(board.cards_remaining(CardType.bystander),
                         BYSTANDER_CARD_COUNT)
        self.assertEqual(board.cards_remaining(CardType.assassin),
                         ASSASSIN_CARD_COUNT)

    def test_reveal(self):
        board = GameBoard(self.word_deck, self.spy_key)
        cards_remaining_before = board.cards_remaining(
            self.starting_team.card_type())
        i, j = self.card_type_coordinates[self.starting_team.card_type()]
        card_type = board.reveal_card_by_coordinates(i, j)
        cards_remaining_after = board.cards_remaining(
            self.starting_team.card_type())
        self.assertEqual(cards_remaining_before, cards_remaining_after + 1)
        self.assertEqual(card_type, self.starting_team.card_type())

    def test_game_over(self):
        board = GameBoard(self.word_deck, self.spy_key)
        card_type_coordinates = self.find_all_card_type_coordinates(
            self.spy_key, self.starting_team.card_type())
        for i, j in card_type_coordinates:
            board.reveal_card_by_coordinates(i, j)
        self.assertTrue(board.team_won(self.starting_team))


if __name__ == '__main__':
    unittest.main()
