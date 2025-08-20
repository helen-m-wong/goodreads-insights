import pandas as pd

# returns total number of books tagged as 'read'
def get_total_read(read_df):
    return len(read_df)

# returns most read author(s) & metadata
def get_most_read_authors(read_df, max_authors=3):
    # no books marked "read" or "Author" column is missing
    if read_df.empty or "Author" not in read_df.columns:
        return {
            "authors" : [],
            "count" : 0,
            "tie" : False,
            "limited" : False
        }
    
    author_counts = read_df["Author"].value_counts()
    max_count = int(author_counts.max())

    # list of authors with the max count
    most_read = author_counts[author_counts == max_count].index.tolist()

    tie = len(most_read) > 1
    limited = False

    # limit to top 3 authors if too many ties
    if tie and len(most_read) > max_authors:
        most_read = most_read[:max_authors]
        limited = True

    return {
        "authors": most_read,
        "count": max_count,
        "tie": tie,
        "limited": limited
    }



# returns name of longest book read
# returns name of shortest book read
# returns name of book that took longest to read
# returns name of book that took shortest to read
# returns average rating of read books
# returns number of 5 star reads
# returns most read genre