import i18n from "@/i18n";

export const timeElapsed = (dateTimeString: string | undefined): string => {
  if (!dateTimeString) {
    return "";
  }

  const givenDate = new Date(dateTimeString);
  const now = new Date();

  const diffInMs = Math.abs(now.getTime() - givenDate.getTime());

  const minutes = Math.floor(diffInMs / (1000 * 60));
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  const months = Math.floor(days / 30); // Approximate
  const years = Math.floor(months / 12);

  if (years > 0) {
    return i18n.t("timeElapse.year", { count: years });
  } else if (months > 0) {
    return i18n.t("timeElapse.month", { count: months });
  } else if (days > 0) {
    return i18n.t("timeElapse.day", { count: days });
  } else if (hours > 0) {
    return i18n.t("timeElapse.hour", { count: hours });
  } else if (minutes > 0) {
    return i18n.t("timeElapse.minute", { count: minutes });
  } else {
    return i18n.t("timeElapse.lessThanAMinute");
  }
};
