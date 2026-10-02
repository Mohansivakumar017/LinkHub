import { useEffect, useState } from "react";

const storageKey = "linkhub_organization_id";
const changeEvent = "linkhub:organization-changed";

export function useSelectedOrganization() {
  const [organizationId, setOrganizationId] = useState(
    () => localStorage.getItem(storageKey) ?? "",
  );

  useEffect(() => {
    const handleChange = (event: Event) => {
      const detail = (event as CustomEvent<string>).detail;
      setOrganizationId(detail ?? "");
    };
    window.addEventListener(changeEvent, handleChange);
    return () => window.removeEventListener(changeEvent, handleChange);
  }, []);

  function selectOrganization(id: string) {
    setOrganizationId(id);
    if (id) {
      localStorage.setItem(storageKey, id);
    } else {
      localStorage.removeItem(storageKey);
    }
    window.dispatchEvent(new CustomEvent(changeEvent, { detail: id }));
  }

  return { organizationId, selectOrganization };
}
