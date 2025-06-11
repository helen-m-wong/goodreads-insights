import pandas as pd
from backend.stats import get_total_read

class TestGetTotalRead:
    def test_all_read(self):
        # all books are marked as 'read'
        data = {
            "Exclusive Shelf": ["read", "read", "read"]
        }
        df = pd.DataFrame(data)
        assert get_total_read(df) == 3

    def test_some_read(self):
        # only some books are marked as 'read'
        data = {
            "Exclusive Shelf": ["currently-reading", "read", "read", "to-read"]
        }
        df = pd.DataFrame(data)
        # simulates filtering for 'read'
        read_df = df[df['Exclusive Shelf'].str.lower() == 'read']
        assert get_total_read(read_df) == 2

    def test_none_read(self):
        # no books are marked as 'read'
        data = {
            "Exclusive Shelf": []
        }
        df = pd.DataFrame(data)
        assert get_total_read(df) == 0

