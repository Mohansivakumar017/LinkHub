import { BrowserRouter } from "react-router-dom";
import { AppRouter } from "./app/router";

/** Frontend composition root. Feature pages and shared providers live below it. */
export default function App() {
  return (
    <BrowserRouter>
      <AppRouter />
    </BrowserRouter>
  );
}
