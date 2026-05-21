import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useMemo } from "react";
import { Controller, useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { useGetRefreshFlowsQuery } from "@/controllers/API/queries/flows/use-get-refresh-flows-query";
import {
  usePatchTrigger,
  usePostTrigger,
} from "@/controllers/API/queries/triggers";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { Trigger } from "../types";
import CronScheduleField from "./CronScheduleField";

// Curated list of common IANA timezones. The user can still type any
// IANA name via the "Other" option which switches to a free-text
// input. Keeping a curated list avoids dragging the full ~600 zones
// from moment-timezone into the dropdown for a marginal use case.
const COMMON_TIMEZONES = [
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "America/Sao_Paulo",
  "America/Argentina/Buenos_Aires",
  "America/Mexico_City",
  "Europe/London",
  "Europe/Berlin",
  "Europe/Paris",
  "Europe/Madrid",
  "Asia/Tokyo",
  "Asia/Shanghai",
  "Asia/Kolkata",
  "Australia/Sydney",
];

const TIMEZONE_OTHER = "__other__";

// Minimal client-side cron sanity check. We deliberately keep the
// canonical validation on the backend (croniter) — this only catches
// obvious format mistakes before the round-trip.
const CRON_FIELD = /^(\*|\?|[0-9*/,\-LW#]+)$/;
const cronLooksValid = (value: string) =>
  value.trim().split(/\s+/).length === 5 &&
  value.trim().split(/\s+/).every((f) => CRON_FIELD.test(f));

const formSchema = z.object({
  flow_id: z.string().uuid({ message: "select a flow" }),
  name: z.string().min(1, { message: "name is required" }).max(255),
  cron_expression: z
    .string()
    .min(1, { message: "cron is required" })
    .refine(cronLooksValid, { message: "5-field cron expected, e.g. */5 * * * *" }),
  timezone: z.string().min(1),
  payload: z
    .string()
    .optional()
    .refine(
      (v) => {
        if (!v || v.trim() === "") return true;
        try {
          const parsed = JSON.parse(v);
          return typeof parsed === "object" && parsed !== null;
        } catch {
          return false;
        }
      },
      { message: "payload must be valid JSON or empty" },
    ),
  max_attempts: z.coerce.number().int().min(1).max(10),
  is_active: z.boolean(),
});

type FormValues = z.infer<typeof formSchema>;

interface TriggerFormModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  existingTrigger: Trigger | null;
}

export default function TriggerFormModal({
  open,
  setOpen,
  existingTrigger,
}: TriggerFormModalProps) {
  const { t } = useTranslation();
  const flows = useFlowsManagerStore((s) => s.flows);
  const setErrorData = useAlertStore((s) => s.setErrorData);
  const setSuccessData = useAlertStore((s) => s.setSuccessData);

  const isEditing = existingTrigger !== null;

  // Make sure the flow selector has data even if the user landed on
  // /triggers without visiting the home page first. The query also
  // hydrates the flowsManagerStore that the table uses to render
  // flow names.
  useGetRefreshFlowsQuery(
    { get_all: true, remove_example_flows: true },
    { enabled: open && (flows === undefined || flows.length === 0) },
  );

  const flowOptions = useMemo(
    () =>
      (flows ?? [])
        .filter((f) => !f.is_component)
        .map((f) => ({ id: f.id, name: f.name })),
    [flows],
  );

  const defaultValues: FormValues = useMemo(
    () => ({
      flow_id: existingTrigger?.flow_id ?? "",
      name: existingTrigger?.name ?? "",
      cron_expression: existingTrigger?.cron_expression ?? "*/5 * * * *",
      timezone: existingTrigger?.timezone ?? "UTC",
      payload: existingTrigger?.payload
        ? JSON.stringify(existingTrigger.payload, null, 2)
        : "",
      max_attempts: existingTrigger?.max_attempts ?? 3,
      is_active: existingTrigger?.is_active ?? true,
    }),
    [existingTrigger],
  );

  const {
    register,
    handleSubmit,
    control,
    reset,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues,
  });

  useEffect(() => {
    if (open) reset(defaultValues);
  }, [open, defaultValues, reset]);

  const currentTimezone = watch("timezone");
  const isCustomTimezone = !COMMON_TIMEZONES.includes(currentTimezone);

  const { mutate: createTrigger } = usePostTrigger({
    onSuccess: () => {
      setSuccessData({ title: t("triggers.createSuccess") });
      setOpen(false);
    },
    onError: (err) =>
      setErrorData({
        title: t("triggers.createError"),
        list: [String((err as Error)?.message ?? err)],
      }),
  });

  const { mutate: patchTrigger } = usePatchTrigger({
    onSuccess: () => {
      setSuccessData({ title: t("triggers.updateSuccess") });
      setOpen(false);
    },
    onError: (err) =>
      setErrorData({
        title: t("triggers.updateError"),
        list: [String((err as Error)?.message ?? err)],
      }),
  });

  const onSubmit = (values: FormValues) => {
    const payload = values.payload?.trim()
      ? JSON.parse(values.payload)
      : null;
    if (isEditing && existingTrigger) {
      patchTrigger({
        trigger_id: existingTrigger.id,
        patch: {
          name: values.name,
          cron_expression: values.cron_expression,
          timezone: values.timezone,
          payload,
          max_attempts: values.max_attempts,
          is_active: values.is_active,
        },
      });
      return;
    }
    createTrigger({
      flow_id: values.flow_id,
      name: values.name,
      cron_expression: values.cron_expression,
      timezone: values.timezone,
      payload,
      max_attempts: values.max_attempts,
      is_active: values.is_active,
    });
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {isEditing ? t("triggers.editTitle") : t("triggers.createTitle")}
          </DialogTitle>
        </DialogHeader>

        <form
          onSubmit={handleSubmit(onSubmit)}
          className="flex flex-col gap-4 py-2"
        >
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="flow_id">{t("triggers.field.flow")}</Label>
            <Controller
              name="flow_id"
              control={control}
              render={({ field }) => (
                <Select
                  value={field.value}
                  onValueChange={field.onChange}
                  disabled={isEditing}
                >
                  <SelectTrigger id="flow_id" data-testid="trigger-flow-select">
                    <SelectValue
                      placeholder={t("triggers.field.flowPlaceholder")}
                    />
                  </SelectTrigger>
                  <SelectContent>
                    {flowOptions.map((flow) => (
                      <SelectItem key={flow.id} value={flow.id}>
                        {flow.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
            {errors.flow_id && (
              <span className="text-xs text-destructive">
                {errors.flow_id.message}
              </span>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="name">{t("triggers.field.name")}</Label>
            <Input
              id="name"
              data-testid="trigger-name-input"
              {...register("name")}
              placeholder={t("triggers.field.namePlaceholder")}
            />
            {errors.name && (
              <span className="text-xs text-destructive">
                {errors.name.message}
              </span>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label>{t("triggers.field.cron")}</Label>
            <Controller
              name="cron_expression"
              control={control}
              render={({ field }) => (
                <CronScheduleField
                  value={field.value}
                  onChange={field.onChange}
                  error={errors.cron_expression?.message}
                />
              )}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="timezone">{t("triggers.field.timezone")}</Label>
            <Controller
              name="timezone"
              control={control}
              render={({ field }) => {
                const selectValue = isCustomTimezone ? TIMEZONE_OTHER : field.value;
                return (
                  <>
                    <Select
                      value={selectValue}
                      onValueChange={(v) => {
                        if (v === TIMEZONE_OTHER) {
                          setValue("timezone", "");
                          return;
                        }
                        field.onChange(v);
                      }}
                    >
                      <SelectTrigger id="timezone">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {COMMON_TIMEZONES.map((tz) => (
                          <SelectItem key={tz} value={tz}>
                            {tz}
                          </SelectItem>
                        ))}
                        <SelectItem value={TIMEZONE_OTHER}>
                          {t("triggers.field.timezoneOther")}
                        </SelectItem>
                      </SelectContent>
                    </Select>
                    {isCustomTimezone && (
                      <Input
                        value={field.value}
                        onChange={(e) => field.onChange(e.target.value)}
                        placeholder="Continent/City"
                      />
                    )}
                  </>
                );
              }}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="max_attempts">
                {t("triggers.field.maxAttempts")}
              </Label>
              <Input
                id="max_attempts"
                type="number"
                min={1}
                max={10}
                {...register("max_attempts", { valueAsNumber: true })}
              />
              {errors.max_attempts && (
                <span className="text-xs text-destructive">
                  {errors.max_attempts.message}
                </span>
              )}
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="is_active">
                {t("triggers.field.isActive")}
              </Label>
              <Controller
                name="is_active"
                control={control}
                render={({ field }) => (
                  <div className="flex h-10 items-center">
                    <Switch
                      id="is_active"
                      checked={field.value}
                      onCheckedChange={field.onChange}
                    />
                  </div>
                )}
              />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="payload">{t("triggers.field.payload")}</Label>
            <Textarea
              id="payload"
              data-testid="trigger-payload-input"
              className="font-mono text-xs"
              rows={4}
              placeholder='{"input_value": "hello"}'
              {...register("payload")}
            />
            <span className="text-xs text-muted-foreground">
              {t("triggers.field.payloadHint")}
            </span>
            {errors.payload && (
              <span className="text-xs text-destructive">
                {errors.payload.message}
              </span>
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
            >
              {t("triggers.cancel")}
            </Button>
            <Button
              type="submit"
              variant="default"
              loading={isSubmitting}
              data-testid="trigger-submit-button"
            >
              {isEditing ? t("triggers.save") : t("triggers.create")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
