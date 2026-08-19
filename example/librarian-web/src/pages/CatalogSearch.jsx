import { useState } from "react";
import { api, ApiError } from "../api/client";

// Search the catalogue, see how many copies are on the shelf, and place a hold
// for a member on the phone. Availability is fetched per expanded row rather
// than for the whole result page: a page of 25 books would be 25 extra calls,
// and the librarian looks at one.
export default function CatalogSearch() {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("idle"); // idle | loading | content | empty | error
  const [results, setResults] = useState([]);
  const [detail, setDetail] = useState(null); // {book, availability, holds}
  const [error, setError] = useState(null);
  const [memberId, setMemberId] = useState("");

  const search = async (event) => {
    event.preventDefault();
    setStatus("loading");
    setError(null);
    try {
      const data = await api.searchBooks(query.trim());
      setResults(data.items);
      setStatus(data.items.length ? "content" : "empty");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "the catalogue is unreachable");
      setStatus("error");
    }
  };

  const expand = async (book) => {
    const [availability, holds] = await Promise.all([
      api.availability(book.id),
      api.bookHolds(book.id),
    ]);
    setDetail({ book, availability, holds: holds.items });
  };

  const hold = async (book) => {
    try {
      const placed = await api.placeHold(book.id, memberId.trim());
      setError(null);
      setDetail((d) => (d ? { ...d, holds: [...d.holds, placed] } : d));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "the hold was not placed");
    }
  };

  return (
    <main className="catalog">
      <form onSubmit={search}>
        <input
          aria-label="Search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Title or author"
        />
      </form>

      {error && <p role="alert" className="banner error">{error}</p>}
      {status === "empty" && <p className="empty">Nothing found.</p>}

      <ul>
        {results.map((book) => (
          <li key={book.id}>
            <button onClick={() => expand(book)}>
              {book.title} — {book.author}, {book.year}
            </button>
            {detail?.book.id === book.id && (
              <div className="detail">
                <p>
                  {detail.availability.available_copies} of{" "}
                  {detail.availability.total_copies} on the shelf,{" "}
                  {detail.holds.length} in the holds queue
                </p>
                <input
                  aria-label="Member card"
                  value={memberId}
                  onChange={(e) => setMemberId(e.target.value)}
                  placeholder="Member card"
                />
                <button onClick={() => hold(book)}>Place hold</button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </main>
  );
}
