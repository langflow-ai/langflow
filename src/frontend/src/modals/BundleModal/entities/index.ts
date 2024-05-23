import { z } from "zod";

export const FolderFormsSchema = z.object({
  name: z.string().min(1, {
    message: "Name must be at least 1 characters.",
  }),
  description: z.string().optional(),
  components: z.array(z.string()),
  flows: z.array(z.string()),
});
