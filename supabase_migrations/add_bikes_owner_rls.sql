-- Run in Supabase SQL Editor — lets showroom owners insert/update/delete their bikes
-- when the API uses the user's access token (anon key + JWT). Service role still bypasses RLS.

-- Bikes: owner CRUD (authenticated showroom owners / admins)
DROP POLICY IF EXISTS "Active owners insert own bikes" ON public.bikes;
CREATE POLICY "Active owners insert own bikes"
  ON public.bikes FOR INSERT
  TO authenticated
  WITH CHECK (
    owner_id = auth.uid()
    AND EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid()
        AND p.role IN ('showroom_owner', 'admin')
        AND p.status = 'active'
    )
  );

DROP POLICY IF EXISTS "Owners update own bikes" ON public.bikes;
CREATE POLICY "Owners update own bikes"
  ON public.bikes FOR UPDATE
  TO authenticated
  USING (
    owner_id = auth.uid()
    AND EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid()
        AND p.role IN ('showroom_owner', 'admin')
        AND p.status = 'active'
    )
  )
  WITH CHECK (owner_id = auth.uid());

DROP POLICY IF EXISTS "Owners delete own bikes" ON public.bikes;
CREATE POLICY "Owners delete own bikes"
  ON public.bikes FOR DELETE
  TO authenticated
  USING (
    owner_id = auth.uid()
    AND EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid()
        AND p.role IN ('showroom_owner', 'admin')
        AND p.status = 'active'
    )
  );

-- Storage: upload + public read for bike-images bucket
DROP POLICY IF EXISTS "Authenticated upload bike images" ON storage.objects;
CREATE POLICY "Authenticated upload bike images"
  ON storage.objects FOR INSERT
  TO authenticated
  WITH CHECK (bucket_id = 'bike-images');

DROP POLICY IF EXISTS "Owners update bike images" ON storage.objects;
CREATE POLICY "Owners update bike images"
  ON storage.objects FOR UPDATE
  TO authenticated
  USING (bucket_id = 'bike-images')
  WITH CHECK (bucket_id = 'bike-images');

DROP POLICY IF EXISTS "Public read bike images" ON storage.objects;
CREATE POLICY "Public read bike images"
  ON storage.objects FOR SELECT
  TO public
  USING (bucket_id = 'bike-images');
