import { api, ApiError } from "../api/client";

// Duplicated from LOAN_PERIOD_DAYS in loans-service/config.py so the desk can
// show a due date before the server answers. If the library changes the loan
// period, this constant has to change with it — the preview is the only thing
// that reads it.
export const LOAN_PERIOD_DAYS = 21;

export const initialState = {
  status: "idle", // idle | loading | content | error
  memberId: "",
  blocked: false,
  loans: [],
  lastAction: null, // {kind: "checkout"|"return"|"renew", loan, nextHold}
  error: null,
};

export function duePreview(today = new Date()) {
  const due = new Date(today);
  due.setDate(due.getDate() + LOAN_PERIOD_DAYS);
  return due.toISOString().slice(0, 10);
}

export function reduce(state, event) {
  switch (event.type) {
    case "member/loading":
      return { ...state, status: "loading", memberId: event.memberId, error: null };
    case "member/loaded":
      return { ...state, status: "content", loans: event.items, blocked: event.blocked };
    case "action/done":
      return { ...state, status: "content", lastAction: event.action, error: null };
    case "failed":
      return { ...state, status: state.loans.length ? "content" : "error", error: event.error };
    case "reset":
      return initialState;
    default:
      return state;
  }
}

// Thin wrappers: one request, one event. The desk stays on the member it is
// showing even when an action fails, so the librarian can read the message and
// try the next book.
export async function loadMember(dispatch, memberId) {
  dispatch({ type: "member/loading", memberId });
  try {
    const data = await api.memberLoans(memberId);
    dispatch({ type: "member/loaded", items: data.items, blocked: data.blocked });
  } catch (error) {
    dispatch({ type: "failed", error: describe(error) });
  }
}

export async function checkoutCopy(dispatch, memberId, barcode) {
  try {
    const loan = await api.checkout(barcode, memberId);
    dispatch({ type: "action/done", action: { kind: "checkout", loan } });
    await loadMember(dispatch, memberId);
  } catch (error) {
    dispatch({ type: "failed", error: describe(error) });
  }
}

export async function returnCopy(dispatch, memberId, loanId) {
  try {
    const result = await api.returnLoan(loanId);
    dispatch({
      type: "action/done",
      action: { kind: "return", loan: result.loan, nextHold: result.next_hold },
    });
    await loadMember(dispatch, memberId);
  } catch (error) {
    dispatch({ type: "failed", error: describe(error) });
  }
}

export async function renewLoan(dispatch, memberId, loanId) {
  try {
    const loan = await api.renew(loanId);
    dispatch({ type: "action/done", action: { kind: "renew", loan } });
    await loadMember(dispatch, memberId);
  } catch (error) {
    dispatch({ type: "failed", error: describe(error) });
  }
}

function describe(error) {
  if (error instanceof ApiError) return error.message;
  return "the service is unreachable";
}
