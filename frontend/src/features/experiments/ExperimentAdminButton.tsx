import { useEffect, useState, type FormEvent } from "react";
import { KeyRound, Lock, Unlock } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { clearExperimentAdminSecret, getExperimentAdminSecret, setExperimentAdminSecret, subscribeExperimentAdmin } from "./admin";
import { verifyExperimentAdmin } from "./api";

export function ExperimentAdminButton() {
  const [open, setOpen] = useState(false);
  const [secret, setSecret] = useState("");
  const [unlocked, setUnlocked] = useState(!!getExperimentAdminSecret());
  const [error, setError] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);

  useEffect(() => subscribeExperimentAdmin(() => setUnlocked(!!getExperimentAdminSecret())), []);

  async function unlock(event: FormEvent) {
    event.preventDefault();
    setVerifying(true);
    setError(null);
    try {
      const response = await verifyExperimentAdmin(secret);
      if (!response.authenticated) {
        clearExperimentAdminSecret();
        setError("Password incorrect.");
        return;
      }
      setExperimentAdminSecret(secret);
      setSecret("");
      setOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to verify password.");
    } finally {
      setVerifying(false);
    }
  }

  function lock() {
    clearExperimentAdminSecret();
    setSecret("");
    setError(null);
    setOpen(false);
  }

  return (
    <>
      <Button
        type="button"
        variant={unlocked ? "secondary" : "outline"}
        size="icon"
        onClick={() => setOpen(true)}
        aria-label={unlocked ? "Experiment admin unlocked" : "Unlock experiment admin"}
        title={unlocked ? "Experiment admin unlocked" : "Unlock experiment admin"}
      >
        {unlocked ? <Unlock className="h-5 w-5" /> : <Lock className="h-5 w-5" />}
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <KeyRound className="h-5 w-5" />
              Experiment Admin
            </DialogTitle>
            <DialogDescription>
              Unlock to save experiment runs and delete saved history in this browser session.
            </DialogDescription>
          </DialogHeader>
          {unlocked ? (
            <div className="space-y-4">
              <p className="rounded-md border bg-slate-50 p-3 text-sm dark:bg-slate-900/40">
                Admin is unlocked. New experiment runs will be saved by default.
              </p>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                  Close
                </Button>
                <Button type="button" variant="destructive" onClick={lock}>
                  Lock
                </Button>
              </DialogFooter>
            </div>
          ) : (
            <form onSubmit={unlock} className="space-y-4">
              <label className="space-y-1 text-sm">
                <span className="font-medium">Secret</span>
                <Input
                  type="password"
                  value={secret}
                  onChange={(event) => setSecret(event.target.value)}
                  autoFocus
                />
              </label>
              {error && <p className="text-sm text-red-600">{error}</p>}
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={verifying || !secret}>
                  Unlock
                </Button>
              </DialogFooter>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
