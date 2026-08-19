// The only place librarian-web builds a URL. Both services sit behind the same
// reverse proxy, which adds the staff session cookie; nothing here sends a
// token of its own.
const CATALOG = "/catalog";
const LOANS = "/loans";

async function call(method, path, body) {
  const response = await fetch(path, {
    method,
    credentials: "same-origin",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!response.ok) {
    // Every service answers {"error": "..."} — the message is shown verbatim.
    throw new ApiError(response.status, payload?.error ?? "unexpected error");
  }
  return payload;
}

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

export const api = {
  searchBooks: (q, page = 1) =>
    call("GET", `${CATALOG}/api/books?q=${encodeURIComponent(q)}&page=${page}`),
  availability: (bookId) => call("GET", `${CATALOG}/api/books/${bookId}/availability`),
  bookHolds: (bookId) => call("GET", `${LOANS}/api/books/${bookId}/holds`),
  placeHold: (bookId, memberId) =>
    call("POST", `${LOANS}/api/holds`, { book_id: bookId, member_id: memberId }),
  memberLoans: (memberId) => call("GET", `${LOANS}/api/members/${memberId}/loans`),
  checkout: (barcode, memberId) =>
    call("POST", `${LOANS}/api/loans`, { barcode, member_id: memberId }),
  renew: (loanId) => call("POST", `${LOANS}/api/loans/${loanId}/renew`),
  returnLoan: (loanId) => call("POST", `${LOANS}/api/loans/${loanId}/return`),
};
