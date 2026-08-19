import { useReducer, useState } from "react";
import {
  checkoutCopy,
  duePreview,
  initialState,
  loadMember,
  reduce,
  renewLoan,
  returnCopy,
} from "../state/checkoutState";

// The desk a librarian keeps open all day: one member at a time, one barcode
// at a time. The barcode field holds focus after every action, because the
// scanner types into whatever is focused and a lost focus means a lost scan.
export default function CheckoutDesk() {
  const [state, dispatch] = useReducer(reduce, initialState);
  const [memberInput, setMemberInput] = useState("");
  const [barcode, setBarcode] = useState("");

  const onMember = (event) => {
    event.preventDefault();
    loadMember(dispatch, memberInput.trim());
  };

  const onScan = async (event) => {
    event.preventDefault();
    await checkoutCopy(dispatch, state.memberId, barcode.trim());
    setBarcode("");
  };

  return (
    <main className="desk">
      <form onSubmit={onMember}>
        <input
          aria-label="Member card"
          value={memberInput}
          onChange={(e) => setMemberInput(e.target.value)}
          placeholder="Scan or type a member card"
        />
      </form>

      {state.error && <p role="alert" className="banner error">{state.error}</p>}
      {state.blocked && (
        <p role="status" className="banner warning">
          This member is blocked. Returns and renewals still work; new loans do not.
        </p>
      )}

      {state.status === "content" && (
        <>
          <form onSubmit={onScan}>
            <input
              autoFocus
              aria-label="Barcode"
              value={barcode}
              onChange={(e) => setBarcode(e.target.value)}
              placeholder="Scan a barcode"
            />
            <span className="hint">Due {duePreview()}</span>
          </form>

          {state.loans.length === 0 ? (
            <p className="empty">Nothing on loan.</p>
          ) : (
            <table>
              <tbody>
                {state.loans.map((loan) => (
                  <tr key={loan.id} className={loan.state}>
                    <td>{loan.barcode}</td>
                    <td>{loan.due_on}</td>
                    <td>{loan.renewals_left} renewals left</td>
                    <td>
                      <button onClick={() => renewLoan(dispatch, state.memberId, loan.id)}>
                        Renew
                      </button>
                      <button onClick={() => returnCopy(dispatch, state.memberId, loan.id)}>
                        Return
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}

      {state.lastAction?.nextHold && (
        <p role="status" className="banner">
          Put copy {state.lastAction.nextHold.barcode} on the hold shelf for
          {" "}{state.lastAction.nextHold.member_id}.
        </p>
      )}
    </main>
  );
}
